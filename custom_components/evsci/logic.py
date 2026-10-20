"""EVSCI: čista odločitvena logika (brez Home Assistanta).

Funkcije v tem modulu ne berejo stanj, ne kličejo storitev in ne uporabljajo
ure: vse, kar potrebujejo, dobijo prek ``Settings`` in ``Inputs``. Zato jih je
mogoče preizkusiti z navadnimi unit testi. Koordinator samo prebere stanja,
pokliče ``decide()`` in izvede ukaze.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from .const import (
    MODE_DYNAMIC,
    MODE_MAX_POWER,
    MODE_MIN_PV,
    MODE_OFF,
    MODE_PV_ONLY,
    MODE_LOW_TARIFF,
    MODE_SCHEDULE,
)

# Korak dviga toka med polnjenjem (velja le, ko tok že teče).
RAMP_UP_STEP = 2.0
# Po zagonu (ali nadaljevanju iz pavze) senzor moči polnilnika zamuja za
# dejanskim tokom, zato v tem času moč polnilnika ocenimo iz ukazanega toka.
STARTUP_GRACE_SECONDS = 15.0
# Nad to močjo štejemo, da polnilnik dejansko polni.
CHARGING_POWER_THRESHOLD_W = 50.0


# Načini, ki upoštevajo limit trenutnega tarifnega bloka.
BLOCK_MODES = (MODE_DYNAMIC, MODE_SCHEDULE, MODE_LOW_TARIFF)


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
    # Zaščita varovalke po posamezni fazi (potrebuje tokove na L1-L3).
    per_phase: bool = False
    # Na kateri fazi (0 = L1, 1 = L2, 2 = L3) je polnilnik; pri 3-faznem
    # polnilniku se uporabi samo kot začetek, obremenjene so vse tri.
    charger_phase: int = 0

    @property
    def power_per_amp(self) -> float:
        """Moč (W), ki jo porabi 1 A na vseh fazah polnilnika."""
        return self.voltage * self.phases

    @property
    def house_phases(self) -> int:
        """Število faz hiše: pri zaščiti po fazah je hiša vedno 3f (polnilnik je lahko 1f)."""
        return 3 if self.per_phase else self.phases

    @property
    def loaded_phases(self) -> tuple[int, ...]:
        """Indeksi faz (0-2), ki jih polnilnik obremenjuje."""
        return tuple((self.charger_phase + k) % 3 for k in range(min(self.phases, 3)))


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
    # Tok po fazah L1-L3 na priključni točki (A, + = uvoz). ``None`` pomeni, da
    # podatka ni ali je star; pri zaščiti po fazah je to varno stanje (pavza).
    phase_currents: tuple[float, float, float] | None = None
    # Tarifni blok (1-5, višji = ceneje) za način Low Tariff. ``tariff_known`` je False,
    # kadar senzorja tarife ni ali še ni dal veljavne vrednosti: takrat ne polnimo.
    tariff_block: int = 1
    low_tariff_block: int = 3
    tariff_known: bool = True


@dataclass(frozen=True)
class Decision:
    """Rezultat izračuna."""

    target_amps: float         # tok, ki naj ga nastavimo (0 = ni polnjenja)
    session_active: bool       # ali naj seja teče
    pv_only_paused: bool       # novo stanje PV-only pavze
    safety_amps_limit: float   # največji tok, ki ga varovalka/blok še dovoli
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


def phase_headroom_amps(settings: Settings, inp: Inputs, charger_power_eff: float) -> tuple[int, int]:
    """Največji tok polnilnika, ki ga najšibkejša faza še prenese.

    Vrne (za vzdrževanje, za dvig). Za dvig odštejemo še buffer.

    Za vsako fazo, ki jo polnilnik obremenjuje, izračunamo hišno obremenitev brez
    polnilnika: ``I_hiša = I_faza - I_polnilnik``. Tok polnilnika po fazah
    ocenimo iz njegove moči (enakomerno čez obremenjene faze). Tok faze vzamemo
    s predznakom: izvoz (negativen tok) fazi res pusti več prostora, senzor, ki
    javlja samo velikost toka, pa je vedno ``>= 0`` in se obravnava kot uvoz
    (previdno, nikoli ne preceni prostora).
    """
    currents = inp.phase_currents
    if currents is None:
        raise ValueError("phase_headroom_amps requires phase_currents")
    loaded = settings.loaded_phases
    charger_amps = max(0.0, charger_power_eff) / (settings.voltage * len(loaded))
    buffer_amps = settings.buffer_watts / settings.power_per_amp
    worst_house = max(currents[i] - charger_amps for i in loaded)
    maintain = math.floor(settings.max_fuse_amps - worst_house)
    increase = math.floor(settings.max_fuse_amps - worst_house - buffer_amps)
    return maintain, increase


def phase_overload(settings: Settings, inp: Inputs) -> bool:
    """Ali katera od faz, ki jih obremenjuje polnilnik, presega varovalko."""
    currents = inp.phase_currents
    if currents is None:
        return False
    return any(currents[i] > settings.max_fuse_amps for i in settings.loaded_phases)


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

    if mode == MODE_LOW_TARIFF:
        cheap_enough = inp.tariff_known and inp.tariff_block >= inp.low_tariff_block
        return (settings.max_amps if cheap_enough else 0), excess_w

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

    house_ppa = settings.voltage * settings.house_phases
    fuse_limit_w = settings.max_fuse_amps * house_ppa
    if inp.mode in BLOCK_MODES:
        limit_base = inp.block_limit_w
    else:
        limit_base = fuse_limit_w

    limit_increase = limit_base - settings.buffer_watts
    limit_maintain = limit_base
    limit_emergency = limit_base + settings.buffer_watts

    # --- Ciljni tok načina ---
    should_session_be_active = not inp.soc_limit_reached
    target_mode_amps: float
    excess_w: float
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

    block_mode = inp.mode in BLOCK_MODES
    per_phase_ok = settings.per_phase and inp.phase_currents is not None
    if per_phase_ok:
        # Skupna omejitev (varovalka oz. blok tarife) velja vedno; zaščita po
        # fazah jo samo dodatno znižuje. Najstrožja omejitev zmaga, tako da
        # preobremenjena ena faza zniža tok polnjenja na vseh fazah.
        phase_maintain, phase_increase = phase_headroom_amps(settings, inp, charger_power_eff)
        amps_limit_maintain = min(amps_limit_maintain, phase_maintain)
        amps_limit_increase = min(amps_limit_increase, phase_increase)
    elif settings.per_phase:
        # Tokov po fazah ni ali so stari: ne vemo, kolikšen je prostor.
        amps_limit_maintain = 0
        amps_limit_increase = 0

    data_unsafe = inp.data_is_stale or (settings.per_phase and inp.phase_currents is None)

    candidate_amps: float
    if data_unsafe:
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
            current_total_amps = (current * ppa + house_load) / house_ppa
            if current_total_amps > settings.max_fuse_amps:
                emergency = True
            if inp.mode != MODE_MAX_POWER and inp.grid_power > limit_emergency:
                emergency = True
            if per_phase_ok and phase_overload(settings, inp):
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


# Stanja, ki vedno pomenijo, da polnilnika ne vidimo (kabel obravnavamo kot odklopljen).
ALWAYS_IDLE_STATES = ("unavailable", "unknown")


def parse_idle_statuses(text: object) -> tuple[str, ...]:
    """Iz niza, ločenega z vejicami, naredi seznam statusov mirovanja (brez presledkov, male črke)."""
    if not text:
        return ()
    return tuple(part.strip().lower() for part in str(text).split(",") if part.strip())


def is_idle_status(value: object, idle_statuses: Iterable[str]) -> bool:
    """True, če status pomeni, da kabel ni priklopljen. Velike/male črke in presledki ne štejejo."""
    normalized = str(value).strip().lower()
    return normalized in ALWAYS_IDLE_STATES or normalized in idle_statuses
