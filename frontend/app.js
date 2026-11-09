document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".metric-card");

  cards.forEach((card, index) => {
    card.style.opacity = "0";
    card.style.transform = "translateY(14px)";
    card.style.transition = "opacity 450ms ease, transform 450ms ease";
    setTimeout(() => {
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    }, 140 + index * 130);
  });

  const navButtons = document.querySelectorAll(".nav-item");
  navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      navButtons.forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
    });
  });
});
