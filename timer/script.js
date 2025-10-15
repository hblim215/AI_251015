const clockEl = document.getElementById("clock");
const toggleBtn = document.getElementById("toggle-format");

let use24Hour = true;
let timerId = null;

function renderTime() {
  const now = new Date();
  const options = {
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hour12: !use24Hour,
  };
  clockEl.textContent = new Intl.DateTimeFormat("ko-KR", options).format(now);
}

function startTimer() {
  renderTime();
  timerId = setInterval(renderTime, 1000);
}

toggleBtn.addEventListener("click", () => {
  use24Hour = !use24Hour;
  toggleBtn.textContent = use24Hour ? "24시간 형식" : "12시간 형식";
  toggleBtn.setAttribute("aria-pressed", use24Hour ? "true" : "false");
  renderTime();
});

// Stop the interval when the page is hidden to avoid unnecessary work.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearInterval(timerId);
    timerId = null;
  } else if (timerId === null) {
    startTimer();
  }
});

startTimer();
