"""Unit testi za čisto odločitveno logiko (custom_components/evsci/logic.py).

Privzete nastavitve: 3 faze, 230 V -> 690 W na amper, varovalka 25 A (17250 W),
buffer 500 W, interval 30 s, tok 6-32 A.
"""
import pytest

from custom_components.evsci.const import (
    MODE_DYNAMIC,
    MODE_MAX_POWER,
    MODE_MIN_PV,
    MODE_OFF,
    MODE_PV_ONLY,
    MODE_SCHEDULE,
)
from custom_components.evsci.logic import (
    Inputs,
    Settings,
    decide,
    effective_charger_power,
    is_in_grace,
    split_energy_power,
    stable_min_charge_power,
)

PPA = 690  # 230 V * 3 faze
S = Settings()

BASE = dict(
    mode=MODE_MAX_POWER,
    grid_power=3000.0,
    charger_power=0.0,
    current_amps=0.0,
    is_charging=False,
    data_is_stale=False,
    soc_limit_reached=False,
    schedule_active=True,
    block_limit_w=11000.0,
    now=1000.0,
    last_amp_change_time=0.0,      # interval je potekel
    grace_until=0.0,               # brez grace perioda
    last_commanded_amps=0.0,
    pv_only_paused=False,
    session_had_active_charge=False,
)

ELAPSED = 0.0      # last_amp_change_time: pred 1000 s
TOO_SOON = 990.0   # last_amp_change_time: pred 10 s (< 30 s)


def inputs(**overrides) -> Inputs:
    return Inputs(**{**BASE, **overrides})


def charging(current, **overrides) -> Inputs:
    """Polnjenje teče s tokom `current`; moč polnilnika je skladna s tokom."""
    power = current * PPA
    house = overrides.pop("house", 3000.0)
    return inputs(
        is_charging=True,
        current_amps=float(current),
        charger_power=float(power),
        grid_power=float(power + house),
        **overrides,
    )


# ---------------------------------------------------------------- nastavitve

def test_power_per_amp():
    assert Settings().power_per_amp == 690
    assert Settings(phases=1).power_per_amp == 230
    assert Settings(phases=3, voltage=400).power_per_amp == 1200


def test_stable_min_charge_power_is_half_of_min_current_power():
    assert stable_min_charge_power(S) == 6 * 690 * 0.5


# ---------------------------------------------------------------- hladen zagon

def test_max_power_cold_start_uses_highest_safe_current_not_min():
    # varno območje za dvig: (17250 - 500 - 3000) / 690 = 19,9 -> 19 A
    d = decide(S, inputs(mode=MODE_MAX_POWER, grid_power=3000))
    assert d.target_amps == 19
    assert d.session_active is True
    assert not d.emergency


def test_dynamic_cold_start_respects_tariff_block_limit():
    # (11000 - 500 - 2000) / 690 = 12,3 -> 12 A
    d = decide(S, inputs(mode=MODE_DYNAMIC, grid_power=2000, block_limit_w=11000))
    assert d.target_amps == 12
    assert d.session_active is True
    assert d.safety_amps_limit == 13  # (11000 - 2000) / 690 = 13,04


def test_dynamic_block_limit_is_used_instead_of_fuse():
    d_block = decide(S, inputs(mode=MODE_DYNAMIC, grid_power=0, block_limit_w=5000))
    d_fuse = decide(S, inputs(mode=MODE_MAX_POWER, grid_power=0))
    assert d_block.target_amps == 6     # (5000 - 500) / 690 = 6,5
    assert d_fuse.target_amps > d_block.target_amps


def test_schedule_outside_window_does_not_start():
    d = decide(S, inputs(mode=MODE_SCHEDULE, schedule_active=False, grid_power=0))
    assert d.target_amps == 0
    assert d.session_active is False


def test_schedule_inside_window_starts_like_dynamic():
    d_sched = decide(S, inputs(mode=MODE_SCHEDULE, schedule_active=True, grid_power=2000))
    d_dyn = decide(S, inputs(mode=MODE_DYNAMIC, grid_power=2000))
    assert d_sched.target_amps == d_dyn.target_amps == 12
    assert d_sched.session_active is True


def test_max_current_setting_caps_start():
    d = decide(Settings(max_amps=16), inputs(grid_power=0))
    assert d.target_amps == 16


def test_single_phase_installation():
    # 230 W/A, varovalka 25 A = 5750 W: (5750 - 500 - 0) / 230 = 22,8 -> 22 A
    d = decide(Settings(phases=1), inputs(grid_power=0))
    assert d.target_amps == 22


def test_not_enough_headroom_does_not_start():
    # hiša že porablja skoraj vse: (16750 - 16000) / 690 = 1 A < 6 A
    d = decide(S, inputs(grid_power=16000))
    assert d.target_amps == 0
    assert d.session_active is False


def test_mode_off_does_nothing():
    d = decide(S, inputs(mode=MODE_OFF, is_charging=True, current_amps=16, charger_power=11000))
    assert d.target_amps == 0
    assert d.session_active is False
    assert d.pv_only_paused is False


# ---------------------------------------------------------------- Min + PV

def test_min_pv_starts_at_minimum_without_surplus():
    d = decide(S, inputs(mode=MODE_MIN_PV, grid_power=0))
    assert d.target_amps == 6
    assert d.session_active is True


def test_min_pv_adds_surplus_on_top_of_minimum():
    # višek 9000 W -> 13 A
    d = decide(S, inputs(mode=MODE_MIN_PV, grid_power=-9000))
    assert d.target_amps == 13


# ---------------------------------------------------------------- dvig toka med polnjenjem

def test_ramp_up_during_charging_is_limited_to_2_amps_per_interval():
    d = decide(S, charging(10, mode=MODE_MAX_POWER))
    assert d.target_amps == 12


def test_ramp_up_waits_for_control_interval():
    d = decide(S, charging(10, mode=MODE_MAX_POWER, last_amp_change_time=TOO_SOON))
    assert d.target_amps == 10


def test_ramp_up_stops_at_safe_target():
    # varno območje za dvig je 19 A, od 18 A ne gremo čez
    d = decide(S, charging(18, mode=MODE_MAX_POWER))
    assert d.target_amps == 19


def test_ramp_up_does_not_exceed_safe_target_when_already_there():
    d = decide(S, charging(19, mode=MODE_MAX_POWER))
    assert d.target_amps == 19


# ---------------------------------------------------------------- grace period

def test_grace_period_estimates_charger_power_from_commanded_current():
    inp = inputs(now=1000, grace_until=1010, last_commanded_amps=19, charger_power=0)
    assert is_in_grace(inp)
    assert effective_charger_power(S, inp) == 19 * PPA


def test_grace_period_keeps_measured_power_when_higher():
    inp = inputs(now=1000, grace_until=1010, last_commanded_amps=10, charger_power=9000)
    assert effective_charger_power(S, inp) == 9000


def test_grace_period_ends_exactly_at_grace_until():
    assert is_in_grace(inputs(now=1009.9, grace_until=1010))
    assert not is_in_grace(inputs(now=1010, grace_until=1010))
    assert effective_charger_power(S, inputs(now=1010, grace_until=1010, last_commanded_amps=19)) == 0


def _late_sensor(grace_until):
    """Takoj po zagonu na 19 A: omrežje že kaže polnjenje, senzor polnilnika še 0 W."""
    return inputs(
        mode=MODE_MAX_POWER,
        is_charging=True,
        current_amps=19.0,
        charger_power=0.0,
        grid_power=3000 + 19 * PPA,
        last_commanded_amps=19.0,
        grace_until=grace_until,
    )


def test_grace_period_prevents_false_overload_after_start():
    d = decide(S, _late_sensor(grace_until=1010))
    assert d.in_grace is True
    assert d.emergency is False
    assert d.target_amps == 19
    assert d.house_load == pytest.approx(3000)


def test_without_grace_period_late_sensor_would_trigger_overload():
    """Kontrola: brez grace perioda bi se hišna poraba napihnila in tok padel."""
    d = decide(S, _late_sensor(grace_until=0))
    assert d.emergency is True
    assert d.target_amps == 6


# ---------------------------------------------------------------- takojšnje znižanje (emergency)

def test_emergency_when_total_current_exceeds_fuse_drops_to_minimum():
    # skupni tok = 20 + 4000 / 690 = 25,8 A > 25 A
    d = decide(S, charging(20, mode=MODE_MAX_POWER, house=4000, last_amp_change_time=TOO_SOON))
    assert d.emergency is True
    assert d.target_amps == 6        # takoj, ne glede na interval


def test_emergency_at_minimum_current_stops_charging():
    d = decide(S, charging(6, mode=MODE_MAX_POWER, house=14000, last_amp_change_time=TOO_SOON))
    assert d.emergency is True
    assert d.target_amps == 0
    assert d.session_active is True    # seja ostane, tok je 0


def test_emergency_when_grid_exceeds_block_limit_plus_buffer():
    # Dynamic: limit bloka 11000 + buffer 500; omrežje 14800 W
    d = decide(S, charging(20, mode=MODE_DYNAMIC, house=1000, last_amp_change_time=TOO_SOON))
    assert d.emergency is True
    assert d.target_amps == 6


def test_max_power_ignores_block_limit_for_emergency():
    # omrežje presega limit bloka, a ne varovalke: v Max Power ni emergency
    d = decide(S, charging(10, mode=MODE_MAX_POWER, house=1000, block_limit_w=5000))
    assert d.emergency is False


def _dynamic_slightly_over(last_change):
    """Dynamic, izvoz hiše: omrežje točno na limitu emergency, kandidat 19 A < 20 A."""
    return inputs(
        mode=MODE_DYNAMIC,
        is_charging=True,
        current_amps=20.0,
        charger_power=20 * PPA,
        grid_power=11500.0,
        block_limit_w=11000.0,
        last_amp_change_time=last_change,
    )


def test_non_emergency_decrease_waits_for_control_interval():
    d = decide(S, _dynamic_slightly_over(TOO_SOON))
    assert d.emergency is False
    assert d.target_amps == 20


def test_non_emergency_decrease_applies_after_control_interval():
    d = decide(S, _dynamic_slightly_over(ELAPSED))
    assert d.emergency is False
    assert d.target_amps == 19


def test_decrease_is_immediate_when_not_charging():
    d = decide(S, inputs(grid_power=16000, current_amps=10, is_charging=False))
    assert d.target_amps == 0


# ---------------------------------------------------------------- stari podatki

def test_stale_data_pauses_charging_after_interval():
    d = decide(S, charging(12, data_is_stale=True))
    assert d.target_amps == 0
    assert d.session_active is True    # seja ostane, tok je 0


def test_stale_data_holds_current_until_interval_elapsed():
    d = decide(S, charging(12, data_is_stale=True, last_amp_change_time=TOO_SOON))
    assert d.target_amps == 12


def test_stale_data_does_not_start_charging():
    d = decide(S, inputs(data_is_stale=True))
    assert d.target_amps == 0
    assert d.session_active is False


# ---------------------------------------------------------------- Target SoC

def test_soc_limit_stops_session_while_charging():
    d = decide(S, charging(12, soc_limit_reached=True))
    assert d.session_active is False
    assert d.target_amps == 0


def test_soc_limit_stops_session_even_before_interval_elapsed():
    d = decide(S, charging(12, soc_limit_reached=True, last_amp_change_time=TOO_SOON))
    assert d.session_active is False


def test_soc_limit_prevents_start():
    d = decide(S, inputs(soc_limit_reached=True, grid_power=0))
    assert d.target_amps == 0
    assert d.session_active is False


def test_soc_limit_clears_pv_only_pause():
    d = decide(S, inputs(mode=MODE_PV_ONLY, soc_limit_reached=True, pv_only_paused=True, is_charging=True))
    assert d.pv_only_paused is False


# ---------------------------------------------------------------- PV only

def test_pv_only_cold_start_uses_highest_current_the_surplus_allows():
    # višek 9000 W = 13 A, z bufferjem (9000 - 500) / 690 = 12 A
    d = decide(S, inputs(mode=MODE_PV_ONLY, grid_power=-9000))
    assert d.target_amps == 12
    assert d.session_active is True
    assert d.pv_only_paused is False


def test_pv_only_does_not_start_below_minimum_plus_buffer():
    # 3000 W višek < 6 A (4140 W) + buffer 500 W
    d = decide(S, inputs(mode=MODE_PV_ONLY, grid_power=-3000))
    assert d.target_amps == 0
    assert d.session_active is False
    assert d.pv_only_paused is False


def test_pv_only_start_threshold_is_minimum_plus_buffer():
    below = decide(S, inputs(mode=MODE_PV_ONLY, grid_power=-4639))
    at = decide(S, inputs(mode=MODE_PV_ONLY, grid_power=-4640))
    assert below.target_amps == 0
    assert at.target_amps == 6


def test_pv_only_ramps_up_in_2_amp_steps_while_charging():
    # višek 10280 W (14 A), tok 10 A -> +2 A
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=10.0,
        charger_power=10 * PPA, grid_power=10 * PPA - 10280,
    )
    assert decide(S, inp).target_amps == 12


def test_pv_only_ramp_up_waits_for_interval():
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=10.0,
        charger_power=10 * PPA, grid_power=10 * PPA - 10280, last_amp_change_time=TOO_SOON,
    )
    assert decide(S, inp).target_amps == 10


def test_pv_only_follows_surplus_down_after_interval():
    # tok 14 A, hiša zdaj uvaža 3000 W: višek 6660 W = 9 A
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=14.0,
        charger_power=14 * PPA, grid_power=3000,
    )
    assert decide(S, inp).target_amps == 9
    inp_soon = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=14.0,
        charger_power=14 * PPA, grid_power=3000, last_amp_change_time=TOO_SOON,
    )
    assert decide(S, inp_soon).target_amps == 14


def test_pv_only_pauses_when_surplus_below_minimum_current():
    # višek 3000 W = 4 A < 6 A -> tok 0, seja ostane, pavza
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=8.0,
        charger_power=8 * PPA, grid_power=8 * PPA - 3000,
    )
    d = decide(S, inp)
    assert d.target_amps == 0
    assert d.pv_only_paused is True
    assert d.session_active is True


def test_pv_only_stays_paused_without_enough_surplus():
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=0.0,
        charger_power=0.0, grid_power=-3000, pv_only_paused=True,
    )
    d = decide(S, inp)
    assert d.target_amps == 0
    assert d.pv_only_paused is True


def test_pv_only_resumes_immediately_at_highest_current_when_surplus_returns():
    # višek 6000 W; z bufferjem (6000 - 500) / 690 = 7 A, brez ramp-upa od 6 A
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=0.0,
        charger_power=0.0, grid_power=-6000, pv_only_paused=True,
    )
    d = decide(S, inp)
    assert d.target_amps == 7
    assert d.pv_only_paused is False


def test_pv_only_ignores_late_charger_power_while_paused():
    """Med pavzo senzor moči polnilnika zamuja in navidezno doda ~4 kW viška."""
    inp = inputs(
        mode=MODE_PV_ONLY, is_charging=True, current_amps=0.0,
        charger_power=6 * PPA, grid_power=-1000, pv_only_paused=True,
    )
    d = decide(S, inp)
    assert d.target_amps == 0
    assert d.pv_only_paused is True


def test_pv_only_caps_at_max_current_setting():
    d = decide(Settings(max_fuse_amps=40), inputs(mode=MODE_PV_ONLY, grid_power=-40000))
    assert d.target_amps == 32


def test_pv_only_leaves_pause_state_untouched_in_other_modes():
    d = decide(S, inputs(mode=MODE_DYNAMIC, pv_only_paused=True, grid_power=0))
    assert d.pv_only_paused is False


# ---------------------------------------------------------------- varnostni limit

def test_safety_amps_limit_is_capped_by_fuse():
    d = decide(S, inputs(grid_power=-20000))
    assert d.safety_amps_limit == 25


def test_safety_amps_limit_subtracts_house_load():
    # (17250 - 3000) / 690 = 20,6 -> 20 A
    d = decide(S, inputs(grid_power=3000))
    assert d.safety_amps_limit == 20
    assert d.house_load == 3000


# ---------------------------------------------------------------- energija

@pytest.mark.parametrize(
    "charger, grid, expected_grid, expected_solar",
    [
        (2000, -500, 0, 2000),     # izvoz: vse iz sonca
        (2000, 0, 0, 2000),        # nič uvoza: vse iz sonca
        (2000, 500, 500, 1500),    # delni uvoz
        (2000, 2000, 2000, 0),     # vse iz omrežja
        (2000, 3000, 2000, 0),     # hiša uvaža še več: polnilnik v celoti iz omrežja
        (0, 3000, 0, 0),           # polnilnik ne polni
        (-50, 3000, 0, 0),         # negativna moč se ignorira
    ],
)
def test_split_energy_power(charger, grid, expected_grid, expected_solar):
    assert split_energy_power(charger, grid) == (expected_grid, expected_solar)


@pytest.mark.parametrize("grid", [-5000, -100, 0, 100, 1999, 2000, 8000])
def test_split_energy_power_shares_sum_to_charger_power(grid):
    g, s = split_energy_power(2000, grid)
    assert g + s == 2000
    assert g >= 0 and s >= 0
