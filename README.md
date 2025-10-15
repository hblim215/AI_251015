# Adorable World Timer

귀여운 세계 시계 인터페이스입니다. 원하는 도시를 클릭해서 시간대를 바꾸고, 언어를 바꾸면서 AM/PM 스타일의 시계를 확인할 수 있습니다.

### Features / 기능
- Pastel, rounded styling with playful animations whenever minutes or seconds change.
- Language toggle button (`한국어 ↔ English`) that live-updates labels and aria text.
- AM/PM digital clock with milliseconds, current date, and GMT offset.
- Clickable world map: select from major cities (Seoul, Tokyo, Sydney, Dubai, London, New York, Los Angeles, Sao Paulo, Johannesburg).
- Automatic day/night marker colors per city based on the current local time.
- Legend and accessibility-friendly descriptions for each interactive control.

### Usage / 사용 방법
1. Open `timer/index.html` in a modern browser (Chrome, Edge, Safari, or Firefox).
2. Tap the pastel language pill to switch interface language.
3. Click a city bubble on the map to change the clock to that timezone.
4. Watch the milliseconds roll underneath the seconds—seconds/minutes trigger a pop animation.

### Project Structure
- `timer/index.html` – main markup and world map SVG.
- `timer/style.css` – pastel theme, map styling, and key animations.
- `timer/script.js` – language handling, timezone math, marker updates, and clock render loop.
