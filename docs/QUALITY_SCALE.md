# Home Assistant Integration Quality Scale: pregled EVSCI

Stanje: veja `devcl`, 18. 10. 2026. Pravila so vzeta iz `script/hassfest/quality_scale.py` v Home Assistant core (20 bronze, 10 silver, 21 gold, 3 platinum).

**Kako je bilo preverjeno:** branje kode in dokumentacije. Pravega Home Assistanta v tem okolju ni bilo mogoče namestiti (gradnja odvisnosti `PyRIC` ne uspe), zato **hassfest ni bil zagnan** in HA testi niso bili izvedeni. Vse ocene je zato treba potrditi s hassfestom, še posebej zahteve za `data_description`, `iot_class` in strukturo manifesta, ki jih navajam po spominu na pravila in ne po zagnanem preverjanju.

Za custom integracije lestvica ni obvezna. Vseeno je dobra merilna letev in za HACS pomaga `hassfest` ter urejen manifest.

Legenda: **OK** izpolnjeno, **DELNO**, **TODO**, **N/A** (izvzeto z razlogom, v `quality_scale.yaml` kot `exempt`).

## Povzetek

| Stopnja | OK | Delno | TODO | N/A |
|---|---|---|---|---|
| Bronze (20) | 5 | 3 | 6 | 6 |
| Silver (10) | 3 | 1 | 4 | 2 |
| Gold (21) | 0 | 2 | 14 | 5 |
| Platinum (3) | 0 | 0 | 1 | 2 |

Bronze je po moji grobi oceni oddaljen približno en delovni dan dela. Največji kos je testno pokritje (config flow, setup, entitete) z `pytest-homeassistant-custom-component`, ki ga je treba zagnati na stroju z delujočo namestitvijo.

## Bronze

| Pravilo | Ocena | Opomba |
|---|---|---|
| action-setup | N/A | Integracija nima lastnih akcij (servisov). |
| appropriate-polling | DELNO | Koordinator se izvaja vsakih 5 s, a bere samo stanja iz HA (brez omrežnih klicev) in je regulacijska zanka. Utemeljeno, a `iot_class` v manifestu je `local_polling`; pravilneje je `calculated`. |
| brands | OK | Mapa `brand/` z icon, logo in dark_logo (+ @2x) za HA 2026.3+. |
| common-modules | DELNO | Koordinator je v `coordinator.py`, entitete po platformah. Manjka skupni osnovni razred `entity.py`, ki bi nosil `DeviceInfo` in `has_entity_name`. |
| config-flow | DELNO | Nastavitev poteka prek UI. Manjkajo `data_description` za polja (hassfest to zahteva); sedaj imajo polja samo oznake. |
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
| runtime-data | TODO | Uporablja se `hass.data[DOMAIN]`; pravilo zahteva `entry.runtime_data` s tipiziranim `ConfigEntry`. |
| test-before-configure | TODO | Config flow ne preveri, da izbrane entitete obstajajo in so berljive. |
| test-before-setup | TODO | `async_config_entry_first_refresh` je klican, a koordinator napake požre in nikoli ne sproži `ConfigEntryNotReady`/`UpdateFailed`. Pri manjkajoči entiteti se nastavitev izvede brez opozorila. |
| unique-config-entry | TODO | Ni `async_set_unique_id`; isto konfiguracijo je mogoče dodati večkrat. |

## Silver

| Pravilo | Ocena | Opomba |
|---|---|---|
| action-exceptions | N/A | Brez lastnih akcij. Klici servisov na polnilnik (`number.set_value`, `button.press`) v koordinatorju niso zaviti v obravnavo napak; to je izboljšava, ne zahteva pravila. |
| config-entry-unloading | OK | `async_unload_entry` obstaja in sprošča platforme. |
| docs-configuration-parameters | OK | README, razdelek Parameters. |
| docs-installation-parameters | OK | README, razdelek Required Sensors. |
| entity-unavailable | DELNO | Entitete ostanejo vedno razpoložljive, tudi kadar vhodnih senzorjev ni. Zavestna odločitev (koordinator preide v varno stanje), a jo je treba sprejeti kot izjemo ali izboljšati. |
| integration-owner | TODO | `codeowners` v manifestu je prazen. |
| log-when-unavailable | TODO | Opozorilo o starih podatkih omrežja se piše **ob vsakem ciklu (5 s)**, brez sporočila ob vrnitvi. Opozorila za tok in faze so enkratna in pravilna, a tudi ta nimajo sporočila ob vrnitvi. |
| parallel-updates | TODO | Platforme `select`, `number`, `time` nimajo `PARALLEL_UPDATES`. |
| reauthentication-flow | N/A | Ni avtentikacije. |
| test-coverage | TODO | Zahtevano >95 %. Pokrita je samo `logic.py` (112 testov). Koordinator, config flow in entitete niso pokriti s HA testi. |

## Gold

| Pravilo | Ocena | Opomba |
|---|---|---|
| devices | TODO | Entitete nimajo `DeviceInfo`, zato ni naprave. Obstoječi `entity_id` in `unique_id` se ne spremenijo. |
| diagnostics | TODO | Ni `diagnostics.py`. |
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
| entity-category | TODO | Nobena entiteta nima `entity_category` (npr. nadzorni senzorji kot diagnostika). |
| entity-device-class | DELNO | Moč in energija imata razred; `Target Current` bi lahko imel `CURRENT`. |
| entity-disabled-by-default | TODO | Nobena entiteta ni privzeto onemogočena (npr. dnevni/življenjski delitveni senzorji). |
| entity-translations | TODO | Imena entitet so trdo zapisana v angleščini (`_attr_name`); potrebna sta `translation_key` in razdelek `entity` v prevodih (en, sl). |
| exception-translations | N/A | Uporabniku ne sprožamo izjem; napake so v config flowu (že prevedene). |
| icon-translations | TODO | Ikone so v `_attr_icon`; pravilo zahteva `icons.json`. |
| reconfiguration-flow | TODO | Obstaja samo options flow; zahtevan je `async_step_reconfigure`. |
| repair-issues | TODO | Npr. opozorilo "Low Tariff brez senzorja tarife" ali trajen izpad senzorja faze bi lahko bil Repair. |
| stale-devices | N/A | Ena naprava, ni dinamičnih. |

## Platinum

| Pravilo | Ocena | Opomba |
|---|---|---|
| async-dependency | N/A | Ni knjižnic. |
| inject-websession | N/A | Ni spletnih klicev. |
| strict-typing | TODO | Tipiziranje je delno (`logic.py` je tipiziran); koordinator in entitete ne, brez `mypy --strict`. |

## Ugotovitve zunaj lestvice

- `manifest.json`: manjka `issue_tracker` (HACS ga priporoča), `codeowners` je prazen, `iot_class` bi moral biti `calculated`.
- Repozitorij nima CI (`.github/workflows`): hassfest, HACS validacija in `pytest` bi morali teči ob vsakem pushu.
- `async_add_entities(..., True)` v platformah sproži nepotreben `update_before_add`; pri entitetah koordinatorja ni potreben.
- Vse je preverjeno samo z unit testi in stubi; nič še ni bilo preizkušeno na pravem HA.

## Predlagan vrstni red (iz plana ugotovitev)

1. **Hitre zmage, majhno tveganje:** `codeowners`, `issue_tracker`, `iot_class`, `PARALLEL_UPDATES`, log-when-unavailable (enkratno opozorilo + sporočilo ob vrnitvi), unique config entry, `data_description` v obeh prevodih.
2. **Bronze/Silver strukturno:** `runtime_data`, `entity.py` z `DeviceInfo` (naprava), `test-before-configure`/`test-before-setup` (ConfigEntryNotReady).
3. **Gold uporabniška izkušnja:** entity translations + `icons.json`, kategorije in privzeto onemogočene entitete, diagnostika, reconfigure flow, repair issues.
4. **Dokumentacija:** razdelki odstranitev, posodabljanje podatkov, omejitve, podprti polnilniki, odpravljanje težav, primeri.
5. **Testi in CI:** HA testi (config flow, setup, entitete) na stroju s pravim HA, hassfest + HACS action v GitHub Actions, nato `quality_scale.yaml` in `mypy --strict` za Platinum.

Pomembno: točke 1 do 3 spreminjajo vedenje HA (naprava, imena entitet, enolični ključ konfiguracije). Brez pravega HA ne morem potrditi, da obstoječe namestitve (entity_id, zgodovina energijskih števcev) ostanejo nedotaknjene, zato bi te korake preizkusil na tvojem HA, preden gredo v izdajo.
