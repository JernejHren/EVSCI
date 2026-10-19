# Home Assistant Integration Quality Scale: pregled EVSCI

Stanje: veja `devcl`, 18. 10. 2026. Pravila so vzeta iz `script/hassfest/quality_scale.py` v Home Assistant core (20 bronze, 10 silver, 21 gold, 3 platinum).

**Kako je bilo preverjeno:** branje kode in dokumentacije. Pravega Home Assistanta v tem okolju ni bilo mogoče namestiti (gradnja odvisnosti `PyRIC` ne uspe), zato **hassfest ni bil zagnan** in HA testi niso bili izvedeni. Vse ocene je zato treba potrditi s hassfestom, še posebej zahteve za `data_description`, `iot_class` in strukturo manifesta, ki jih navajam po spominu na pravila in ne po zagnanem preverjanju.

Za custom integracije lestvica ni obvezna. Vseeno je dobra merilna letev in za HACS pomaga `hassfest` ter urejen manifest.

Legenda: **OK** izpolnjeno, **DELNO**, **TODO**, **N/A** (izvzeto z razlogom, v `quality_scale.yaml` kot `exempt`).

## Povzetek

| Stopnja | OK | Delno | TODO | N/A |
|---|---|---|---|---|
| Bronze (20) | 12 | 0 | 2 | 6 |
| Silver (10) | 6 | 1 | 1 | 2 |
| Gold (21) | 9 | 1 | 6 | 5 |
| Platinum (3) | 0 | 0 | 1 | 2 |

Bronze je po moji grobi oceni oddaljen približno en delovni dan dela. Največji kos je testno pokritje (config flow, setup, entitete) z `pytest-homeassistant-custom-component`, ki ga je treba zagnati na stroju z delujočo namestitvijo.

## Bronze

| Pravilo | Ocena | Opomba |
|---|---|---|
| action-setup | N/A | Integracija nima lastnih akcij (servisov). |
| appropriate-polling | OK | Koordinator se izvaja vsakih 5 s, a bere samo stanja iz HA (brez omrežnih klicev) in je regulacijska zanka. `iot_class` je zdaj `calculated`. |
| brands | OK | Mapa `brand/` z icon, logo in dark_logo (+ @2x) za HA 2026.3+. |
| common-modules | OK | Koordinator v `coordinator.py`, skupni osnovni razred entitet v `entity.py`, platforme v svojih datotekah. |
| config-flow | OK | Nastavitev prek UI; polja imajo `data_description` (en, sl). Potrditi s hassfestom. |
| config-flow-test-coverage | TODO | Ni testov config flowa z resničnim HA. Obstajajo samo ad hoc preverjanja s stubi. |
| dependency-transparency | N/A | Brez zunanjih knjižnic (`requirements: []`). |
| docs-actions | N/A | Ni akcij. |
| docs-conditions | N/A | Ni pogojev. |
| docs-triggers | N/A | Ni sprožilcev. |
| docs-high-level-description | OK | README. |
| docs-installation-instructions | OK | README: HACS in ročna namestitev. |
| docs-removal-instructions | TODO | Ni opisa odstranitve. |
| entity-event-setup | N/A | Entitete se ne naročajo na dogodke; podatke dobijo prek koordinatorja. |
| entity-unique-id | OK | Vse entitete imajo `unique_id`, osnovan na `entry_id`. |
| has-entity-name | OK | `_attr_has_entity_name = True` povsod. |
| runtime-data | OK | `entry.runtime_data` s tipom `EVSCIConfigEntry`; `hass.data` se ne uporablja več. |
| test-before-configure | OK | Config in options flow preverita, da izbrane entitete (in senzorji faz) obstajajo; sicer napaka `entity_not_found`. Preverjeno s stubi. |
| test-before-setup | OK | Če manjka omrežni senzor, tok ali moč polnilnika, `async_setup_entry` sproži `ConfigEntryNotReady` in HA poskusi znova. Preverjeno s stubi. |
| unique-config-entry | OK | `unique_id` je entiteta za nastavitev toka polnilnika; drugi vnos za isti polnilnik se zavrne. Obstoječi vnosi brez `unique_id` niso zaščiteni. |

## Silver

| Pravilo | Ocena | Opomba |
|---|---|---|
| action-exceptions | N/A | Brez lastnih akcij. Klici servisov na polnilnik (`number.set_value`, `button.press`) v koordinatorju niso zaviti v obravnavo napak; to je izboljšava, ne zahteva pravila. |
| config-entry-unloading | OK | `async_unload_entry` obstaja in sprošča platforme. |
| docs-configuration-parameters | OK | README, razdelek Parameters. |
| docs-installation-parameters | OK | README, razdelek Required Sensors. |
| entity-unavailable | DELNO | Entitete ostanejo vedno razpoložljive, tudi kadar vhodnih senzorjev ni. Zavestna odločitev (koordinator preide v varno stanje), a jo je treba sprejeti kot izjemo ali izboljšati. |
| integration-owner | OK | `codeowners`: `@JernejHren`. |
| log-when-unavailable | OK | Opozorilo za senzor omrežja, tok polnilnika in tokove po fazah se zapiše enkrat ob izpadu, ob vrnitvi pa sporočilo (INFO). Preverjeno s simulacijo. |
| parallel-updates | OK | `PARALLEL_UPDATES = 0` v vseh platformah. |
| reauthentication-flow | N/A | Ni avtentikacije. |
| test-coverage | TODO | Zahtevano >95 %. Pokrita je samo `logic.py` (112 testov). Koordinator, config flow in entitete niso pokriti s HA testi. |

## Gold

| Pravilo | Ocena | Opomba |
|---|---|---|
| devices | OK | Vse entitete pripadajo ena napravi "EV Smart Charging" (`DeviceInfo`, `entry_type=SERVICE`). `unique_id` se niso spremenili. |
| diagnostics | OK | `diagnostics.py`: nastavitve, notranje stanje, zadnji rezultat in stanja vhodnih entitet. Preverjeno s stubi. |
| discovery | N/A | Ni odkrivanja (virtualna integracija). |
| discovery-update-info | N/A | Isto. |
| docs-data-update | TODO | README ne opisuje, kako in kako pogosto se podatki osvežujejo. |
| docs-examples | DELNO | Obstaja primer dashboard kartice; manjkajo primeri avtomatizacij. |
| docs-known-limitations | TODO | Ni razdelka (npr. testirano samo z ABB Terra AC, en polnilnik, predpostavka predznaka toka). |
| docs-supported-devices | TODO | Ni seznama podprtih polnilnikov. |
| docs-supported-functions | TODO | Funkcije so v README, a ne kot seznam entitet. |
| docs-troubleshooting | TODO | Ni razdelka. |
| docs-use-cases | TODO | Ni razdelka. |
| dynamic-devices | N/A | Ena naprava. |
| entity-category | OK | Nastavitvene entitete (number, time) so `CONFIG`, nadzorna senzorja `DIAGNOSTIC`. |
| entity-device-class | OK | Moč `POWER`, energija `ENERGY`, ciljni tok `CURRENT`. Tarifni blok nima ustreznega razreda. |
| entity-disabled-by-default | OK | `Monitored Grid Power` (kopija uporabnikovega senzorja) je privzeto onemogočen. |
| entity-translations | OK | `translation_key` pri vseh entitetah, imena v `translations/en.json` in `sl.json`. |
| exception-translations | N/A | Uporabniku ne sprožamo izjem; napake so v config flowu (že prevedene). |
| icon-translations | OK | `icons.json`; v kodi ni več `_attr_icon` ali `icon` lastnosti. |
| reconfiguration-flow | OK | `async_step_reconfigure` (+ korak s fazami). Shrani podatke, počisti options in zavrne polnilnik, ki ga že uporablja drug vnos. Preverjeno s stubi. |
| repair-issues | OK | Popravki za izpad senzorja omrežja, toka polnilnika ali faze (po 5 min) in za Low Tariff brez senzorja tarife. Odstranijo se ob vrnitvi in ob odstranitvi vnosa. |
| stale-devices | N/A | Ena naprava, ni dinamičnih. |

## Platinum

| Pravilo | Ocena | Opomba |
|---|---|---|
| async-dependency | N/A | Ni knjižnic. |
| inject-websession | N/A | Ni spletnih klicev. |
| strict-typing | TODO | Tipiziranje je delno (`logic.py` je tipiziran); koordinator in entitete ne, brez `mypy --strict`. |

## Ugotovitve zunaj lestvice

- `manifest.json`: `codeowners`, `issue_tracker` in `iot_class` so urejeni (korak 1). `integration_type` ni nastavljen, ker nisem prepričan, katera vrednost ustreza; potrditi s hassfestom.
- Repozitorij nima CI (`.github/workflows`): hassfest, HACS validacija in `pytest` bi morali teči ob vsakem pushu.
- `async_add_entities(..., True)` je odstranjen (nepotreben `update_before_add`).
- Vse je preverjeno samo z unit testi in stubi; nič še ni bilo preizkušeno na pravem HA.

## Predlagan vrstni red (iz plana ugotovitev)

1. **Hitre zmage, majhno tveganje (NAREJENO):** `codeowners`, `issue_tracker`, `iot_class`, `PARALLEL_UPDATES`, log-when-unavailable (enkratno opozorilo + sporočilo ob vrnitvi), unique config entry, `data_description` v obeh prevodih.
2. **Bronze/Silver strukturno (NAREJENO):** `runtime_data`, `entity.py` z `DeviceInfo` (naprava), `test-before-configure`/`test-before-setup` (ConfigEntryNotReady).
3. **Gold uporabniška izkušnja (NAREJENO):** entity translations + `icons.json`, kategorije in privzeto onemogočene entitete, diagnostika, reconfigure flow, repair issues.
4. **Dokumentacija:** razdelki odstranitev, posodabljanje podatkov, omejitve, podprti polnilniki, odpravljanje težav, primeri.
5. **Testi in CI:** HA testi (config flow, setup, entitete) na stroju s pravim HA, hassfest + HACS action v GitHub Actions, nato `quality_scale.yaml` in `mypy --strict` za Platinum.

Pomembno: točke 1 do 3 spreminjajo vedenje HA (naprava, imena entitet, enolični ključ konfiguracije). Brez pravega HA ne morem potrditi, da obstoječe namestitve (entity_id, zgodovina energijskih števcev) ostanejo nedotaknjene, zato bi te korake preizkusil na tvojem HA, preden gredo v izdajo.
