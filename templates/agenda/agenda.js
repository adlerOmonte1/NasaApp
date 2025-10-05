const calendar = document.getElementById('calendar');
const monthYear = document.getElementById('monthYear');
const modal = document.getElementById('eventModal');
const cancelBtn = document.getElementById('cancelBtn');
const saveBtn = document.getElementById('saveBtn');

let selectedDate = null;
let events = JSON.parse(localStorage.getItem('events')) || {};
let date = new Date();

const months = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
];

function renderCalendar() {
  const year = date.getFullYear();
  const month = date.getMonth();
  monthYear.textContent = `${months[month]} ${year}`;
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  calendar.innerHTML = `
    <div class="day-name">Lun</div>
    <div class="day-name">Mar</div>
    <div class="day-name">Mié</div>
    <div class="day-name">Jue</div>
    <div class="day-name">Vie</div>
    <div class="day-name">Sáb</div>
    <div class="day-name">Dom</div>
  `;

  let start = firstDay.getDay();
  if (start === 0) start = 7;

  for (let i = 1; i < start; i++) {
    calendar.innerHTML += `<div></div>`;
  }

  for (let i = 1; i <= lastDay.getDate(); i++) {
    const fullDate = `${year}-${month + 1}-${i}`;
    const dayEvents = events[fullDate] || [];
    let eventHTML = dayEvents.map(e => `<div class="event">${e.title}</div>`).join("");
    calendar.innerHTML += `
      <div class="day" onclick="openModal('${fullDate}')">
        <div class="day-number">${i}</div>
        ${eventHTML}
      </div>`;
  }
}

function openModal(dateStr) {
  selectedDate = dateStr;
  modal.style.display = 'flex';
}

function closeModal() {
  modal.style.display = 'none';
  document.getElementById('eventTitle').value = '';
  document.getElementById('eventDesc').value = '';
}

function saveEvent() {
  const title = document.getElementById('eventTitle').value.trim();
  const desc = document.getElementById('eventDesc').value.trim();
  if (!title) return alert("Por favor ingresa un título");

  if (!events[selectedDate]) events[selectedDate] = [];
  events[selectedDate].push({ title, desc });
  localStorage.setItem('events', JSON.stringify(events));
  closeModal();
  renderCalendar();
}

document.getElementById('prev').addEventListener('click', () => {
  date.setMonth(date.getMonth() - 1);
  renderCalendar();
});

document.getElementById('next').addEventListener('click', () => {
  date.setMonth(date.getMonth() + 1);
  renderCalendar();
});

cancelBtn.addEventListener('click', closeModal);
saveBtn.addEventListener('click', saveEvent);

window.onclick = (e) => {
  if (e.target === modal) closeModal();
};

renderCalendar();
