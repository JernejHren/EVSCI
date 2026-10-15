"""EVSCI: čista odločitvena logika (brez Home Assistanta).

Funkcije v tem modulu ne berejo stanj, ne kličejo storitev in ne uporabljajo
ure: vse, kar potrebujejo, dobijo prek ``Settings`` in ``Inputs``. Zato jih je
mogoče preizkusiti z navadnimi unit testi. Koordinator samo prebere stanja,
pokliče ``decide()`` in izvede ukaze.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .const import (
    MODE_DYNAMIC,
    MODE_MAX_POWER,
    MODE_MIN_PV,
    MODE_OFF,
    MODE_PV_ONLY,
    MODE_SCHEDULE,
)

# Korak dviga toka med polnjenjem (velja le, ko tok že teče).
RAMP_UP_STEP = 2.0
# Po zagonu (ali nadaljevanju iz pavze) senzor moči polnilnika zamuja za
# dejanskim tokom, zato v tem času moč polnilnika ocenimo iz ukazanega toka.
STARTUP_GRACE_SECONDS = 15.0
# Nad to močjo štejemo, da polnilnik dejansko polni.
CHARGING_POWER_THRESHOLD_W = 50.0


@dataclass(frozen=True)
class Settings:
    """Nastavitve instalacije (spreminjajo se samo prek nastavitev integracije)."""

    phases: int = 3
    voltage: float = 230.0
    min_amps: float = 6
    max_amps: float = 32
    max_fuse_amps: float = 25
    buffer_watts: float = 500
    control_interval: float = 30

    @property
    def power_per_amp(self) -> float:
        """Moč (W), ki jo porabi 1 A na vseh fazah."""
        return self.voltage * self.phases


@dataclass(frozen=True)
class Inputs:
    """Stanje sveta v trenutku izračuna."""

    mode: str
    grid_power: float          # neto moč na priključni točki (W), + = uvoz
    charger_power: float       # izmerjena moč polnilnika (W)
    current_amps: float        # trenutno nastavljen tok polnilnika (A)
    is_charging: bool          # seja teče
    data_is_stale: bool        # podatki omrežja so stari ali neberljivi
    soc_limit_reached: bool    # dosežen ciljni SoC
    schedule_active: bool      # trenutni čas je v urniku
    block_limit_w: float       # limit trenutnega tarifnega bloka (W)
    now: float                 # trenutni čas (s)
    last_amp_change_time: float
    grace_until: float         # do kdaj velja grace period po zagonu (s)
    last_commanded_amps: float
    pv_only_paused: bool       # PV-only seja je v pavzi
    session_had_active_charge: bool


@dataclass(frozen=True)
class Decision:
    """Rezultat izračuna."""

    target_amps: float         # tok, ki naj ga nastavimo (0 = ni polnjenja)
    session_active: bool       # ali naj seja teče
    pv_only_paused: bool       # novo stanje PV-only pavze
    safety_amps_limit: int     # največji tok, ki ga varovalka/blok še dovoli
    house_load: float          # hišna poraba brez polnilnika (W)
    charger_power_eff: float   # moč polnilnika, uporabljena v izračunu (W)
    in_grace: bool
    emergency: bool            # sprožena takojšnja zaustavitev zaradi preobremenitve


def is_in_grace(inp: Inputs) -> bool:
    return inp.now < inp.grace_until


def effective_charger_power(settings: Settings, inp: Inputs) -> float:
    """Moč polnilnika za izračun.

    V grace periodu senzor moči še zamuja, zato vzamemo večjo od izmerjene in
    ocenjene moči (ukazani tok × moč na amper). Brez tega bi se hišna poraba
    napihnila in sprožila lažno preobremenitev.
    """
    if is_in_grace(inp):
        return max(inp.charger_power, inp.last_commanded_amps * settings.power_per_amp)
    return inp.charger_power


def stable_min_charge_power(settings: Settings) -> float:
    """Moč, nad katero štejemo, da je polnjenje stabilno steklo."""
    return settings.min_amps * settings.power_per_amp * 0.5


def mode_target_amps(settings: Settings, inp: Inputs, charger_power_eff: float) -> tuple[float, float]:
    """Vrne (želeni tok načina, PV višek v W).

    Višek je neničelen samo v PV načinih.
    """
    mode = inp.mode
    excess_w = 0.0

    if mode in (MODE_MAX_POWER, MODE_DYNAMIC):
        return settings.max_amps, excess_w

    if mode == MODE_SCHEDULE:
        return (settings.max_amps if inp.schedule_active else 0), excess_w

    if mode in (MODE_PV_ONLY, MODE_MIN_PV):
        excess_w = charger_power_eff - inp.grid_power
        if mode == MODE_PV_ONLY and inp.pv_only_paused:
            # Med pavzo ne zaupamo nujno senzorju moči polnilnice, ker lahko
            # zamuja in navidezno doda ~4 kW "viška".
            excess_w = max(0.0, -inp.grid_power)
        solar_amps = min(math.floor(excess_w / settings.power_per_amp), settings.max_amps)
        if mode == MODE_PV_ONLY:
            return solar_amps, excess_w
        return max(settings.min_amps, solar_amps), excess_w

    return 0, excess_w


def decide(settings: Settings, inp: Inputs) -> Decision:
    """Glavna odločitev: kakšen tok in ali naj seja teče."""
    if inp.mode == MODE_OFF:
        return Decision(
            target_amps=0,
            session_active=False,
            pv_only_paused=False,
            safety_amps_limit=0,
            house_load=inp.grid_power - inp.charger_power,
            charger_power_eff=inp.charger_power,
            in_grace=False,
            emergency=False,
        )

    ppa = settings.power_per_amp
    min_amps = settings.min_amps
    current = inp.current_amps

    # --- Limiti moči ---
    in_grace = is_in_grace(inp)
    charger_power_eff = effective_charger_power(settings, inp)
    house_load = inp.grid_power - charger_power_eff

    fuse_limit_w = settings.max_fuse_amps * ppa
    if inp.mode in (MODE_DYNAMIC, MODE_SCHEDULE):
        limit_base = inp.block_limit_w
    else:
        limit_base = fuse_limit_w

    limit_increase = limit_base - settings.buffer_watts
    limit_maintain = limit_base
    limit_emergency = limit_base + settings.buffer_watts

    # --- Ciljni tok načina ---
    should_session_be_active = not inp.soc_limit_reached
    if inp.soc_limit_reached:
        target_mode_amps, excess_w = 0, 0.0
    else:
        target_mode_amps, excess_w = mode_target_amps(settings, inp, charger_power_eff)

    # --- Kandidat ---
    amps_limit_maintain = min(
        math.floor((limit_maintain - house_load) / ppa), settings.max_fuse_amps
    )
    amps_limit_increase = min(
        math.floor((limit_increase - house_load) / ppa), settings.max_fuse_amps
    )

    if inp.data_is_stale:
        candidate_amps = 0
    else:
        candidate_amps = min(target_mode_amps, amps_limit_maintain)

    pv_only_min_start_w = min_amps * ppa + settings.buffer_watts
    pv_only_up_amps = max(0, math.floor((excess_w - settings.buffer_watts) / ppa))

    # Po pavzi v aktivni PV-only seji dovolimo ponovni zagon šele, ko je spet na
    # voljo minimum za najmanjši tok plus buffer.
    if (
        inp.mode == MODE_PV_ONLY
        and inp.pv_only_paused
        and excess_w < pv_only_min_start_w
    ):
        candidate_amps = 0

    # --- Finalizacija ---
    adjusted_amps = current
    emergency = False
    time_since_change = inp.now - inp.last_amp_change_time

    if candidate_amps < current:
        # ZNIŽEVANJE
        if not inp.is_charging:
            # Polnilnica je izklopljena: takoj uporabi kandidata, da ne vklopimo
            # s prevelikim tokom.
            adjusted_amps = candidate_amps
        else:
            current_total_amps = current + (house_load / ppa)
            if current_total_amps > settings.max_fuse_amps:
                emergency = True
            if inp.mode != MODE_MAX_POWER and inp.grid_power > limit_emergency:
                emergency = True

            if emergency:
                adjusted_amps = min_amps if current > min_amps else 0
            elif time_since_change >= settings.control_interval:
                adjusted_amps = candidate_amps
            else:
                adjusted_amps = current

    elif candidate_amps > current:
        # POVEČEVANJE
        safe_target_up = min(target_mode_amps, amps_limit_increase)
        if inp.mode == MODE_PV_ONLY:
            # Histereza: za vsak dvig toka v PV only zahtevamo še buffer.
            safe_target_up = min(safe_target_up, pv_only_up_amps)

        if safe_target_up > current:
            is_startup = current < min_amps and safe_target_up >= min_amps
            is_pv_only_start_blocked = (
                inp.mode == MODE_PV_ONLY
                and current < min_amps
                and (not inp.is_charging or inp.session_had_active_charge)
                and excess_w < pv_only_min_start_w
            )

            if is_pv_only_start_blocked:
                adjusted_amps = 0
            elif not inp.is_charging:
                # Hladen zagon: takoj z največjim varnim tokom (brez ramp-upa).
                adjusted_amps = safe_target_up
            elif is_startup:
                # Nadaljevanje iz pavze: takoj z največjim varnim tokom.
                adjusted_amps = safe_target_up
            elif time_since_change >= settings.control_interval:
                adjusted_amps = min(safe_target_up, current + RAMP_UP_STEP)
            else:
                adjusted_amps = current
        else:
            adjusted_amps = current

    # Minimum
    if adjusted_amps < min_amps:
        adjusted_amps = 0

    # --- PV-only pavza ---
    pv_only_paused = inp.pv_only_paused
    if inp.mode != MODE_PV_ONLY or not should_session_be_active:
        pv_only_paused = False
    elif adjusted_amps == 0 and (
        inp.pv_only_paused
        or current >= min_amps
        or inp.charger_power >= stable_min_charge_power(settings)
    ):
        pv_only_paused = True
    elif inp.pv_only_paused and excess_w >= pv_only_min_start_w and adjusted_amps >= min_amps:
        pv_only_paused = False

    # --- Stanje seje ---
    if inp.is_charging:
        # Če teče, ostane vklopljena, dokler način želi (tudi pri 0 A).
        session_active = should_session_be_active
    else:
        # Če ne teče, se vklopi samo, če imamo dovolj toka (Start Threshold).
        session_active = should_session_be_active and adjusted_amps >= min_amps

    return Decision(
        target_amps=adjusted_amps,
        session_active=session_active,
        pv_only_paused=pv_only_paused,
        safety_amps_limit=amps_limit_maintain,
        house_load=house_load,
        charger_power_eff=charger_power_eff,
        in_grace=in_grace,
        emergency=emergency,
    )


def split_energy_power(charger_power: float, grid_power: float) -> tuple[float, float]:
    """Razdeli moč polnilnika na (omrežje, sonce).

    Model neto števca: brez polnilnika bi omrežje kazalo ``grid - charger``.
    Če je to negativno (izvoz), polnilnik najprej porabi ta izvoz (sonce), ostalo
    pride iz omrežja. Če je pozitivno (hiša že uvaža), je polnilnik v celoti iz
    omrežja. V obeh primerih velja: omrežni delež = ``clamp(grid, 0, charger)``.
    """
    if charger_power <= 0:
        return 0.0, 0.0
    grid_share = min(charger_power, max(0.0, grid_power))
    return grid_share, charger_power - grid_share
