# Genesis Lectures — backup

Architecture Lectures in Pisa

Backup di https://www.genesislectures.com fatto il 2026-10-21 dalla REST API di WordPress (tema Uncode + WPBakery).
Rigenerabile con `python3 -I export.py`.

## Struttura

- `lectures/<anno>/<slug>.md`: una conferenza per file. Frontmatter: anno (= categoria WP), `cancelled` (edizione 2020, rimandata e poi annullata per il COVID-19), tag, `when`/`where` (data e luogo dal box laterale), `excerpt`, date di pubblicazione/modifica, `cover` (immagine in evidenza), `background` (sfondo della testata), `gallery`, `video` (YouTube).
- `pages/`: le pagine (la home è `gl2k19.md`; la pagina Venue era vuota, il suo contenuto sta in `blocks/venue.md`).
- `blocks/`: blocchi Uncode riusati nel layout (footer con le descrizioni delle edizioni, testata home, venue…).
  Dove il sito aveva una versione desktop e una mobile dello stesso blocco è tenuta solo quella desktop.
- `media/AAAA/MM/`: tutti gli originali della media library (stessi percorsi di `wp-content/uploads`, senza le miniature generate da WordPress). `media/svg/`: loghi che il tema salvava come SVG inline.
- `media.json`: metadati di ogni media (titolo, alt, didascalia, data, contenuto a cui è collegato, dimensioni).
- `raw/`: risposte grezze dell'API (contenuti originali con gli shortcode), come rete di sicurezza.

## Licenza

Testi (team di Genesis Lectures) e grafiche (Fabio Santaniello Bruun) sono CC BY-NC 4.0: ripubblicabili citando la fonte, non per scopi commerciali. Le immagini dei progetti restano © degli studi e dei fotografi, `export.py` è MIT. Dettagli in [LICENSE.md](LICENSE.md).

## Conferenze

### 2020 — edizione annullata (COVID-19)

- [noa*](lectures/2020/noa.md) — Fall — Polo Porta Nuova, PN10, Pisa
- [Room11 Architects](lectures/2020/room11-architects.md) — Fall — Polo Porta Nuova, PN10, Pisa
- [Bergmeisterwolf](lectures/2020/bergmeisterwolf.md) — Fall — Polo Porta Nuova, PN10, Pisa

### 2019

- [ARX Portugal](lectures/2019/arx-portugal.md) — Friday 3 May, 4.30 pm — Polo Porta Nuova, PN10, Pisa
- [Vector Architects](lectures/2019/vector-architects.md) — Friday 10 May, 4.30 pm — Polo Porta Nuova, PN10, Pisa
- [Massimo Carmassi](lectures/2019/massimo-carmassi.md) — Friday 8 March, 4.30 pm — Polo Porta Nuova, PN10, Pisa

### 2018

- [Durisch + Nolli](lectures/2018/durisch-nolli.md) — Friday 13 April, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa
- [Robbrecht en Daem](lectures/2018/robbrecht-en-daem.md) — Friday 4 May, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa
- [Carmody Groarke](lectures/2018/carmody-groarke.md) — Friday 18 May, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa

### 2017

- [Sou Fujimoto](lectures/2017/sou-fujimoto.md) — Friday 3 March, h 4.00 pm — Aula Magna, Polo Carmignani, Pisa
- [TAMassociati](lectures/2017/tamassociati.md) — Friday 21 April, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa
- [Elisa Valero Ramos](lectures/2017/elisa-valero-ramos.md) — Friday 12 May, h 4.00 pm — Aula Magna, Polo Carmignani, Pisa

### 2016

- [Tony Fretton](lectures/2016/tony-fretton.md) — Friday 1 April, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa
- [Guillermo Vázquez Consuegra](lectures/2016/guillermo-vazquez-consuegra.md) — Friday 15 April, h 5.00 pm — Aula Magna, Polo Piagge, Pisa
- [Ricardo Bak Gordon](lectures/2016/ricardo-bak-gordon.md) — Friday 29 April, h 5.00 pm — Cinema Nuovo, Pisa
- [Dietmar Eberle](lectures/2016/dietmar-eberle.md) — Friday 6 May, h 5.00 pm — Aula Magna, Polo Carmignani, Pisa

## Immagini fuori dalla media library

Usate nel sito (slider, opzioni del tema) ma non registrate come media:

- `media/2018/11/genesis_lecture-logo.svg`
- `media/2018/11/genesis_logo.svg`
