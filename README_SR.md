# PhotoAgent v2.5

Lokalna aplikacija za pronalaženje i pregled identičnih i vizuelno sličnih
fotografija. Obrada radi bez interneta, naloga, telemetrije i spoljnih AI servisa.
[English installation and usage](README.md).

## Instalacija i pokretanje

Potreban je Python 3.12+ na Windows 10/11 ili Linux sistemu. Na Windowsu pokrenite
`start_windows.bat`; na Linuxu `bash start_linux.sh`. Pokretači proveravaju
zavisnosti i otvaraju PySide6 interfejs. Preuzimanje nedostajućih zavisnosti zahteva
internet ili lokalne pakete. Linux Python i venv se instaliraju zasebno.

Ako su paketi već pripremljeni lokalno, u odabranom virtuelnom okruženju:

```text
python -m pip install --no-index --find-links /putanja/do/paketa -r requirements.txt
python -B photo_agent.py --ui qt
```

Za već instaliran razvojni projekat na Windowsu:

```powershell
.venv/Scripts/python.exe -B photo_agent.py --ui qt
```

Za izgradnju i instalaciju lokalnog ZIP paketa bez interneta pogledajte
[RELEASE.md](docs/RELEASE.md). Paket ne uključuje Python. Validacija na čistom
operativnom sistemu, nativnom Linuxu i sa validnim RAW uzorkom ostaje otvorena.

## Jezik i izgled

Otvorite **Settings → Language** i izaberite **Srpski (latinica)** ili **English**.
Na srpskom se stranica zove **Podešavanja**. Promena se primenjuje odmah, uključujući
otvorene potvrde, poruke o greškama, napredak i oznake za čitače ekrana. Ne potvrđuje
plan i ne poništava izbor fotografija. Izbor se čuva automatski; tokom skeniranja
upis sačeka završetak aktivnog posla. Ako upis ne uspe, vraća se poslednji sačuvani
jezik uz poruku. Postojeća podešavanja bez jezičkog izbora zadržavaju srpski;
nova instalacija počinje na engleskom.

Veličine, broj na kontrolnoj tabli i datumi skeniranja prate izabrani jezik.
Datumi u istoriji ostaju označeni kao UTC. Nazivi datoteka, putanje, formati i
heševi se ne prevode. Nedostajući prevod koristi engleski rezervni tekst.
Tema se bira između tamne, svetle i sistemske. Stari `--ui tk` interfejs ostaje
samo na srpskom i nema promenu jezika tokom rada.

## Bezbedan rad

1. Dodajte izvorne fascikle i pokrenite skeniranje. Nedostupni diskovi i greške
   dekodiranja prikazuju se kao nepotpun rezultat. Skeniranje se može zaustaviti.
2. Pregledajte grupe i uporedite fotografije. EXACT znači identičan SHA-256;
   VISUAL znači sličnost koja zahteva ručni pregled. Sačuvajte važne izmene i RAW.
3. Označite fotografije za zadržavanje i pripremite plan za karantin. Pročitajte
   izvor, odredište i upozorenja. Tek izričita potvrda pokreće premeštanje. Za RAW
   ostaje obavezno unošenje tačnog tokena `RAW`, u oba jezika.
4. Karantin je povratno premeštanje. Istorija omogućava pripremu i potvrdu vraćanja
   na originalnu lokaciju. Postojeće datoteke se nikada ne prepisuju. XMP prateće
   datoteke se ne pomeraju automatski. Kopije na različitim izvorima zahtevaju
   pojedinačni pregled jer mogu biti namerne rezervne kopije.

CSV izveštaji su tehnički izlaz sa stabilnim poljima, nezavisno od jezika ekrana.
Ne menjajte ručno karantin ili dnevnik operacija. Uputstva za oporavak i poznata
ograničenja: [SECURITY.md](docs/SECURITY.md).

## Prevođenje i provera

Uređivi izvori su `app/i18n/en.ts` i `app/i18n/sr_Latn.ts`; mogu se otvoriti u
Qt Linguist alatu. Sačuvajte parametre `{0}` i `%1` bez promene. Izgradnja radi
lokalno sa već instaliranim PySide6 alatima:

```text
python -B -m tools.build_translations
python -B -m tools.build_translations --check
python -B -m pytest -p no:cacheprovider tests/test_localization.py tests/test_task012.py -q
```

Detalji dodavanja jezika, kompilacije, pakovanja i rezervnih prevoda nalaze se u
[LOCALIZATION.md](docs/LOCALIZATION.md); rezultati testova su u
[TESTING.md](docs/TESTING.md).
