# EVSCI: plan dela

Datum: 2026-10-15

## Pregled faz

Plan ima štiri faze: hitri popravki z ramp-upom, testabilna logika, zaščita po fazah in podpora za druge polnilnike (več hkrati je odloženo). Vsaka naslednja faza se naslanja na prejšnjo, zato je vrstni red pomemben.

| Faza | Vsebina | Ocena | Odvisnost |
| --- | --- | --- | --- |
| 1 | Hitri popravki in ramp-up ob zagonu z grace periodom | približno 1–2 dni | brez |
| 2 | Odločitvena logika v čisti funkciji + unit testi | približno 1–2 dni | faza 1 |
| 3 | Zaščita varovalke po fazah (3f) | 1–1,5 dneva | faza 2 |
| 4a | Podpora za druge polnilnike (en po en) | 0,5–1 dan | faza 2 |
| 4b | Več polnilnikov hkrati (odloženo, ni mogoče testirati) | 3–5 dni | faze 2 in 3 |

Ocene za fazi 3 in 4 so iz prejšnjih odgovorov, ocene za fazi 1 in 2 so grobe in jih je treba potrditi.

## Faza 1: hitri popravki in ramp-up

Glavni cilj faze je, da polnjenje začne z največjim možnim tokom glede na razpoložljivo elektriko, ne pa s 6 A in dvigom po 2 A na 30 s (od 6 do 32 A je to približno 6,5 minute).

**Ramp-up ob zagonu**

- [x] Ob hladnem zagonu in nadaljevanju iz pavze uporabi `safe_target_up`, ki je že omejen z varovalko, blokom in bufferom.
- [x] Ob zagonu začni z največjim možnim tokom v vseh načinih. V Dynamic, Max Power in Schedule ramp-up ob začetku popolnoma izključi. V PV načinih ohrani spreminjanje med polnjenjem po 2 A na 30 s, da tok ne skače gor in dol.
- [x] Dodaj grace period (10–15 s) brez emergency zniževanja po zagonu. Senzor polnilnika (Modbus poll) še kaže 0 W, omrežje pa že več kW več, zato bi `house_load` napihnilo in sprožilo lažno "kritično preobremenitev".
- [x] Med grace periodom oceni hišno porabo z zadnjim ukazanim tokom, dokler senzor ne dohiti. Enako velja za `excess_w` v PV-only.

**Popravki napak**

- [x] Zaznava starih podatkov: uporabi `last_reported` namesto `last_updated`, sicer konstantna moč omrežja po 60 s sproži pavzo.
- [x] Dvojno štetje energije: `set_mode()` in zaznava priklopa kličeta `async_set_updated_data(self.data)`, senzorji pa ponovno prištejejo stare prirastke `energy_inc_*`. Prirastke naj porabi samo redni update.
- [x] SoC in tok: namesto `isdigit()` uporabi `float()` v try/except, ob napaki (npr. `unavailable`) pa varno stanje (pavza) namesto tihega privzetka 6 A.
- [x] Goli `except:` zamenjaj z `except (ValueError, TypeError)`.

**Odstranitev solar senzorja**

- [x] Odstrani `CONF_SOLAR_SENSOR` iz `const.py`, `config_flow.py` (shema in `optional_fields`) in `_load_config`.
- [x] Odstrani `self.solar_entity`, `solar_power` v `_async_update_data` ter `EVSCISolarMonitor` v `sensor.py`.
- [x] Odstrani ključ `solar_sensor` iz `en.json` in `sl.json` (config in options).
- [x] Migracije ni: ključ `solar_sensor` v obstoječih vnosih se samo ignorira, `VERSION` ostane 1.

**Higiena repozitorija**

- [x] Izpolni prazen `LICENSE` (Apache License 2.0).
- [x] Popravi README (še omenja "Charger Switch") in dodaj omembo odstranjenega solar senzorja.
- [x] Dopolni CHANGELOG z 0.2.1 in novo verzijo.
- [x] Naredi tarifni senzor neobvezen za uporabnike z eno tarifo.
- [x] Trdo zapisane 230 V, 6 A in 32 A prestavi v nastavitve polnilnika.

## Faza 2: testabilna odločitvena logika

Odločitev o toku se izloči v čisto funkcijo (stanje noter, odločitev ven), ker je to osnova za varno izvedbo faz 3 in 4. Zdaj ima `_async_update_data` okoli 300 vrstic, PV-only pavza pa je state machine, ki ga je težko slediti.

- [x] Definiraj vhodno stanje (meritve, nastavitve, stanje seje, čas) in izhod (ciljni tok, start/stop seje).
- [x] Premakni izračun limitov, kandidata za tok, ramp-up, emergency in PV-only pavzo v čisto funkcijo brez dostopa do `hass`.
- [x] Koordinator naj samo bere stanje, kliče funkcijo in izvaja ukaze.
- [x] Napiši unit teste: hladen zagon, ramp-up v PV načinih, grace period, emergency znižanje, PV-only pavza in nadaljevanje, stari podatki, dosežen Target SoC.
- [x] Pripisovanje energije solar/omrežje pregledano: formula `min(charger_power, max(0, grid_power))` je pri modelu neto števca pravilna (brez polnilnika bi omrežje kazalo `grid - charger`, polnilnik najprej porabi izvoz, ostalo je iz omrežja), zato vedenja nisem spreminjal. Ugotovitev v točki 8 prvotnega pregleda je bila preohlapna. Zapisano je v `split_energy_power()` in pokrito s testi.

## Faza 3: zaščita varovalke po fazah

Pri 3f hiši uporabnik izbere, ali integracija ščiti varovalko po skupni porabi (privzeto) ali po posamezni fazi. Ocena je 1–1,5 delovnega dne.

- [x] Nova nastavitev "Zaščita varovalke" (*Skupna poraba* / *Po fazah*), vidna samo pri `phases = 3`.
- [x] Senzorji toka (A) za L1, L2 in L3, obvezni samo v načinu "Po fazah". Config flow pokaže polja pogojno (dva koraka ali pogojna shema) in prevodi v `en.json` in `sl.json`.
- [x] Izračun po fazah: `I_hiša,Lx = I_Lx − I_polnilnik,Lx`, dovoljen tok polnilnika je minimum čez vse faze, nato velja najstrožja od vseh omejitev.
- [x] Max Power postane "največ, kar prenese najšibkejša faza". Blok tarife in PV višek ostaneta pri skupni (neto) moči.
- [x] Nastavitev faze za enofazni polnilnik na 3f hiši. Pri 3f polnilniku se obremeni vse tri enako.
- [x] Če polnilnik ne daje toka po fazah, uporabi ukazani tok ali skupno moč, deljeno s tremi.
- [x] Predznak toka: uporabljamo podpisane tokove (uvoz +, izvoz −), ker izvoz ne obremeni varovalke kot uvoz. Senzor, ki daje samo velikost, se obravnava kot uvoz (konservativno). Odločitev se je spremenila glede na prvotni načrt (absolutna vrednost).
- [x] Izpad senzorja ene faze: pavza (kot pri starih podatkih), enkratno opozorilo v dnevniku, nikoli tiho ignoriranje.
- [x] Grace period iz faze 1 velja tudi tu.
- [x] Unit testi z neuravnoteženimi scenariji (po izločitvi logike v fazi 2).

Popravek po povratni informaciji: skupna moč in zaščita po fazah veljata hkrati (najstrožja zmaga), ne ena namesto druge. Pri 1f polnilniku na 3f hiši skupni limit računa z 3 fazami (`house_phases`).

Opomba: config flow in prevodi so preverjeni samo s stubi, ne z resničnim Home Assistantom. Na strojni opremi ni testirano.

## Faza 4: več polnilnikov

Koordinator že zdaj govori samo s HA entitetami, zato je podpora za druge polnilnike (en po en) poceni, več hkrati pa je večja predelava.

**4a: drugi polnilniki, en po en (0,5–1 dan)**

- [ ] Nastavljivo preslikovanje statusov "mirovanje" (zdaj trdo zapisani ABB seznami).
- [ ] Nastavljiv min/max tok polnilnika.
- [ ] Izbira med stikalom in gumbi za start/stop.

**4b: več polnilnikov hkrati (3–5 dni), odloženo**

- [ ] Model podatkov: loči lokacijo (omrežje, varovalka, buffer, tarifa, bloki) od polnilnika (start/stop, tok, moč, status, SoC, faze, min/max A, način, urnik), npr. prek config subentries (HA 2025.3+).
- [ ] Koordinator: en na lokacijo, v njem kontroler na polnilnik z lastnim stanjem (seja, PV pavza, čas zadnje spremembe).
- [ ] Razdeljevanje: proračun = limit − hišna poraba (brez vseh polnilnikov), delitev po prioriteti ali enakomerno, minimum 6 A na polnilnik in odločitev, kateri se pavzira. Enako za PV višek.
- [ ] Entitete: mode, Target SoC, urnik in senzorji po polnilniku (device na polnilnik), lokacijski senzorji posebej.
- [ ] Migracija: prvi polnilnik ohrani obstoječe `unique_id` (temeljijo na `entry_id`), sicer uporabniki izgubijo zgodovino in dashboarde.
- [ ] Testiranje razdeljevanja s simulacijo, ker je na pravi opremi verjetno le en polnilnik.

## Odločitve

Vseh šest vprašanj je rešenih.

- Več polnilnikov hkrati: odloženo, ker je na voljo samo en polnilnik in razdeljevanja ni mogoče testirati. Delitev po prioriteti ali enakomerno zaenkrat ni potrebna.
- Senzorji po fazah: tok (A), ker so varovalke podane v A.
- Solar senzor: odstrani, da je namestitev lažja, jasnejša in ne zavaja.
- Migracija solar senzorja: ni je, ključ `solar_sensor` v obstoječih vnosih se samo ignorira in `VERSION` ostane 1.
- PV načini: zagon z največjim možnim tokom, med polnjenjem spreminjanje po 2 A, da tok ne skače gor in dol.
- Dynamic, Max Power in Schedule: ramp-up ob začetku polnjenja je popolnoma izključen.
- Dvig toka med polnjenjem (vsi načini): ostane po največ 2 A na interval, brez večjih skokov.
