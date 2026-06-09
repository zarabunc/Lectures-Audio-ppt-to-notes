# Lecture Enricher

Orodje za generiranje zapiskov iz predavanj: vzame PDF slajdov in posnetek predavanja, s pomočjo Whisperja naredi transkript, Claude API pa semantično poveže dele transkripta s posameznimi slajdi.

**Izhod:**

| Mapa | Vsebina |
|------|---------|
| `output/transcripts/` | Celoten transkript predavanja (Whisper) |
| `output/notes/` | Zapiski PDF — slajdi + ujemajoči del transkripta |
| `output/images/` | Slike slajdov |

---

## Namestitev

```bash
git clone https://github.com/zarabunc/Lectures-Audio-ppt-to-notes.git
cd Lectures-Audio-ppt-to-notes/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Potrebuješ tudi:
- **Anthropic API ključ** — dobi ga na [console.anthropic.com](https://console.anthropic.com)
- **ffmpeg** (za Whisper): `brew install ffmpeg`

---

## Hiter zagon — samo zapiski iz slajdov

Če imaš že PDF slajdov in transkript, poženi samo `merge_notes.py`:

```bash
cd app
source .venv/bin/activate

# API ključ kot argument
python merge_notes.py --api-key sk-ant-...

# ali kot okoljska spremenljivka
export ANTHROPIC_API_KEY=sk-ant-...
python merge_notes.py
```

Skript te bo za API ključ vprašal tudi interaktivno, če ga ne podaš.

### Možnosti

| Argument | Opis | Privzeto |
|----------|------|---------|
| `--api-key` | Anthropic API ključ | `ANTHROPIC_API_KEY` env |
| `--slides` | Pot do PDF slajdov | `input/slides/*.pdf` |
| `--transcript` | Pot do `.txt` datoteke s transkriptom | vsebina `FULL_TRANSCRIPT` v skriptu |
| `--name` | Ime izhodnega PDF | `Lecture test_notes` |

**Primer z vsemi argumenti:**

```bash
python merge_notes.py \
  --api-key sk-ant-... \
  --slides ../input/slides/predavanje.pdf \
  --transcript ../input/transcript.txt \
  --name "Predavanje 1_notes"
```

Izhod: `output/notes/Predavanje 1_notes.pdf`

### Transkript

Transkript podat kot **eno samo besedilo** (ni treba razdeliti po slajdih). Claude sam ugotovi, kateri del transkripta spada k kateremu slajdu glede na vsebino.

Primer `transcript.txt`:
```
Danes si bomo ogledali vrednost inovacij za investitorje...
Elevator pitch je kratek povzetek vašega projekta...
...
```

---

## Celoten pipeline (posnetek → zapiski)

```bash
cd ..   # koren repozitorija
./run.sh --course "Ime predavanja"
```

Če je zvok že v `input/audio/`:

```bash
./run.sh --course "Ime predavanja" --skip-export
```

### Možnosti `run.sh`

| Ukaz | Pomen |
|------|--------|
| `--course "..."` | Ime predavanja |
| `--skip-export` | Preskoči izvoz iz Voice Memos |
| `--whisper-model small` | Natančnejši Whisper (počasneje) |
| `--all` | Obdelaj vse seje brez izbire |

---

## Kako deluje

1. **Whisper** pretvori posnetek predavanja v besedilo
2. **Claude vision** za vsak slajd: prebere besedilo (OCR) + pogleda sliko → naredi povzetek vsebine slajda
3. **Claude** primerja celoten transkript z vsebinami slajdov → semantično priredi dele transkripta k ustreznim slajdom
4. **PyMuPDF** sestavi končni PDF z zapiski (naslovnica + slajdi s transkripcijo)
