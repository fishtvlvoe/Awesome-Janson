(() => {
  const buttons = [...document.querySelectorAll(".filter")];
  const cards = [...document.querySelectorAll(".capability")];
  buttons.forEach((button) => button.addEventListener("click", () => {
    buttons.forEach((item) => item.classList.toggle("is-active", item === button));
    const filter = button.dataset.filter;
    cards.forEach((card) => { card.hidden = filter !== "all" && card.dataset.category !== filter; });
  }));
})();
