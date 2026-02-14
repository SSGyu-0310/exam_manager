(() => {
  const audio = new Audio("/static/audio/duck-quack.mp3");
  audio.preload = "auto";

  window.addEventListener("keydown", (event) => {
    if (event.repeat) return;
    if (event.key !== "ScrollLock" && event.code !== "ScrollLock") return;
    audio.currentTime = 0;
    audio.play().catch(() => {});
  });
})();
