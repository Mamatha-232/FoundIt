const lostForm = document.getElementById("lostForm");
const foundForm = document.getElementById("foundForm");
const lostItemsContainer = document.getElementById("lostItems");
const foundItemsContainer = document.getElementById("foundItems");
const matchResultsContainer = document.getElementById("matchResults");
const messageBox = document.getElementById("messageBox");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const clearButton = document.getElementById("clearButton");
const notificationBox = document.getElementById("notificationBox");
const topNavButtons = document.querySelectorAll(".top-link");
const reportButton = document.getElementById("reportButton");


function showMessage(message, isError = false) {
    messageBox.textContent = message;
    messageBox.style.color = isError ? "#b33232" : "#2a7f62";
}


function showNotification(message) {
    notificationBox.innerHTML = message.replace(/\n/g, "<br>");
    notificationBox.classList.add("show");

    window.clearTimeout(showNotification.timeoutId);
    showNotification.timeoutId = window.setTimeout(() => {
        notificationBox.textContent = "";
        notificationBox.classList.remove("show");
    }, 4000);
}


function notifyUsers() {
    showNotification("\u{1F514} Match found! Notification sent to both users.");
}


function buildEmail(username) {
    if (!username) {
        return "unknown@kitsw.ac.in";
    }

    return `${username}@kitsw.ac.in`;
}


function notifyMatchedUsers(match) {
    showNotification(
        `\u{1F514} Match found!\n\u{1F4E7} Notification sent successfully to matched users`
    );
}


function isValidPhone(phone) {
    const cleanedPhone = phone.trim();
    return /^\d{5,10}$/.test(cleanedPhone);
}


async function submitItem(form, endpoint) {
    const formData = new FormData(form);
    const phone = String(formData.get("phone") || "").trim();

    if (!isValidPhone(phone)) {
        alert("Enter valid phone number (minimum 5 digits)");
        return;
    }

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Something went wrong.");
        }

        form.reset();
        showMessage(data.message);
        await loadItems(searchInput.value.trim());
        await loadMatches();
    } catch (error) {
        showMessage(error.message, true);
    }
}


function createItemCard(item) {
    const card = document.createElement("article");
    card.className = `item-card ${item.type} ${item.status}`;

    card.innerHTML = `
        <div class="item-header">
            <div>
                <h3>${item.name}</h3>
                <p class="meta"><strong>Location:</strong> ${item.location}</p>
                <p class="meta"><strong>Phone:</strong> ${item.phone}</p>
            </div>
            <span class="pill ${item.status}">${item.status}</span>
        </div>
        ${item.image_url ? `<img class="item-image" src="${item.image_url}" alt="${item.name}">` : ""}
        <p>${item.description}</p>
    `;

    if (item.status !== "recovered") {
        const recoverButton = document.createElement("button");
        recoverButton.className = "btn recover-btn";
        recoverButton.textContent = "Mark as Recovered";
        recoverButton.addEventListener("click", async () => {
            await markRecovered(item.id);
        });
        card.appendChild(recoverButton);
    }

    return card;
}


function renderItems(container, items, emptyText) {
    container.innerHTML = "";

    if (!items.length) {
        container.innerHTML = `<div class="empty-state">${emptyText}</div>`;
        return;
    }

    items.forEach((item) => {
        container.appendChild(createItemCard(item));
    });
}


function createMatchCard(match) {
    const card = document.createElement("article");
    card.className = "match-card";

    card.innerHTML = `
        <div class="match-header">
            <div>
                <h3>&#x2705; ${match.message}</h3>
                <p class="meta">The AI found overlapping keywords between these reports.</p>
            </div>
            <span class="pill active">Potential Match</span>
        </div>
        <div class="match-columns">
            <div class="match-box">
                <h4>Lost Item</h4>
                <p><strong>${match.lost_item.name}</strong></p>
                ${match.lost_item.image_url ? `<img class="item-image" src="${match.lost_item.image_url}" alt="${match.lost_item.name}">` : ""}
                <p>${match.lost_item.description}</p>
                <p class="meta"><strong>Location:</strong> ${match.lost_item.location}</p>
                <p class="meta"><strong>Lost by:</strong> ${match.lost_item.phone}</p>
            </div>
            <div class="match-box">
                <h4>Found Item</h4>
                <p><strong>${match.found_item.name}</strong></p>
                ${match.found_item.image_url ? `<img class="item-image" src="${match.found_item.image_url}" alt="${match.found_item.name}">` : ""}
                <p>${match.found_item.description}</p>
                <p class="meta"><strong>Location:</strong> ${match.found_item.location}</p>
                <p class="meta"><strong>Found by:</strong> ${match.found_item.phone}</p>
            </div>
        </div>
        <p class="keywords"><strong>Common keywords:</strong> ${match.common_words.join(", ")}</p>
        <p class="match-status">&#x2705; Match Found</p>
        <button class="btn notify-btn" type="button">Notify Users</button>
    `;

    const notifyButton = card.querySelector(".notify-btn");
    notifyButton.addEventListener("click", () => {
        notifyMatchedUsers(match);
    });

    return card;
}


function renderMatches(matches) {
    matchResultsContainer.innerHTML = "";

    if (!matches.length) {
        matchResultsContainer.innerHTML = `
            <div class="empty-state">
                No match found yet. Matches will appear when item words overlap.
            </div>
        `;
        return;
    }

    matches.forEach((match) => {
        matchResultsContainer.appendChild(createMatchCard(match));
    });
}


async function loadItems(search = "") {
    try {
        const query = search ? `?search=${encodeURIComponent(search)}` : "";
        const response = await fetch(`/items${query}`);
        const data = await response.json();

        renderItems(lostItemsContainer, data.lost_items, "No lost items available.");
        renderItems(foundItemsContainer, data.found_items, "No found items available.");
    } catch (error) {
        showMessage("Unable to load items right now.", true);
    }
}


async function loadMatches() {
    try {
        const response = await fetch("/match");
        const data = await response.json();
        renderMatches(data.matches);
    } catch (error) {
        showMessage("Unable to load matched results right now.", true);
    }
}


async function markRecovered(itemId) {
    try {
        const response = await fetch(`/mark_recovered/${itemId}`, {
            method: "POST",
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to update item.");
        }

        showMessage(data.message);
        await loadItems(searchInput.value.trim());
        await loadMatches();
    } catch (error) {
        showMessage(error.message, true);
    }
}


function scrollToSection(targetId) {
    const targetSection = document.getElementById(targetId);
    if (!targetSection) {
        return;
    }

    targetSection.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}


topNavButtons.forEach((button) => {
    button.addEventListener("click", () => {
        scrollToSection(button.dataset.target);
    });
});


if (reportButton) {
    reportButton.addEventListener("click", () => {
        scrollToSection("report-section");
    });
}


lostForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitItem(lostForm, "/add_lost");
});

foundForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitItem(foundForm, "/add_found");
});

searchButton.addEventListener("click", async () => {
    await loadItems(searchInput.value.trim());
});

clearButton.addEventListener("click", async () => {
    searchInput.value = "";
    showMessage("Search cleared.");
    await loadItems();
});

searchInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
        await loadItems(searchInput.value.trim());
    }
});


async function initializePage() {
    await loadItems();
    await loadMatches();
}


initializePage();
