document.addEventListener("DOMContentLoaded", function () {
    const fileInput = document.querySelector("#resumeFile");
    const uploadBox = document.querySelector("#uploadBox");
    const fileCard = document.querySelector("#fileCard");
    const analyzeButton = document.querySelector("#analyzeButton");
    const statusMessage = document.querySelector("#statusMessage");
    const removeButton = document.querySelector("#removeFile");

    if (!fileInput || !uploadBox || !fileCard || !analyzeButton) {
        return;
    }

    analyzeButton.disabled = true;
    fileCard.hidden = true;

    function setMessage(message, state = "") {
        statusMessage.textContent = message;
        statusMessage.className = `status-message ${state}`.trim();
    }

    function selectFile(file) {
        if (!file) {
            fileInput.value = "";
            fileCard.hidden = true;
            analyzeButton.disabled = true;
            setMessage("Choose a PDF resume to get started.");
            return;
        }

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            fileInput.value = "";
            fileCard.hidden = true;
            analyzeButton.disabled = true;
            setMessage("Only PDF files are allowed.", "error");
            return;
        }

        if (file.size > 25 * 1024 * 1024) {
            fileInput.value = "";
            fileCard.hidden = true;
            analyzeButton.disabled = true;
            setMessage("The PDF must be smaller than 25MB.", "error");
            return;
        }

        document.querySelector("#fileName").textContent = file.name;
        document.querySelector("#fileSize").textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        fileCard.hidden = false;
        analyzeButton.disabled = false;
        setMessage("Ready to analyze your resume.");
    }

    fileInput.addEventListener("change", () => {
        selectFile(fileInput.files[0]);
    });

    uploadBox.addEventListener("click", (event) => {
        if (!event.target.closest(".browse-button")) {
            fileInput.click();
        }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
        uploadBox.addEventListener(eventName, (event) => {
            event.preventDefault();
            uploadBox.classList.add("dragging");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        uploadBox.addEventListener(eventName, (event) => {
            event.preventDefault();
            uploadBox.classList.remove("dragging");
        });
    });

    uploadBox.addEventListener("drop", (event) => {
        const [file] = event.dataTransfer.files;
        if (!file) {
            return;
        }

        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        selectFile(file);
    });

    removeButton.addEventListener("click", () => {
        selectFile(null);
    });

    analyzeButton.addEventListener("click", async () => {
        const file = fileInput.files[0];
        if (!file) {
            setMessage("Choose a PDF resume before analyzing.", "error");
            return;
        }

        analyzeButton.disabled = true;
        analyzeButton.classList.add("analyzing");
        setMessage("Analyzing your resume...");

        const formData = new FormData();
        formData.append("resume", file);

        try {
            const response = await fetch("/upload", {
                method: "POST",
                body: formData
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Resume analysis failed.");
            }

            displayAnalysis(data);
            setMessage("Analysis complete. Your report is ready.", "success");
        } catch (error) {
            setMessage(error.message || "Could not analyze this resume.", "error");
        } finally {
            analyzeButton.disabled = false;
            analyzeButton.classList.remove("analyzing");
        }
    });
});

function displayAnalysis(data) {
    document.querySelector("#scoreValue").textContent = data.score ?? 0;
    document.querySelector("#statusBadge").textContent = data.status || "Analyzed";
    document.querySelector("#summaryStatus").textContent = data.status || "Analyzed";
    document.querySelector("#atsScore").textContent = `${data.ats_score ?? 0}/100`;
    document.querySelector("#strengthCount").textContent = (data.strengths || []).length;
    document.querySelector("#improvementCount").textContent = (data.improvements || []).length;

    const skillsList = document.querySelector("#skillsList");
    skillsList.replaceChildren();
    (data.skills || []).forEach((skill) => {
        const tag = document.createElement("span");
        tag.className = "skill-tag";
        tag.textContent = skill;
        skillsList.appendChild(tag);
    });
    if (!data.skills?.length) {
        skillsList.textContent = "No matching skills detected.";
    }

    renderList("#strengthList", data.strengths || []);
    renderList("#improvementList", data.improvements || []);

    const structureResult = document.querySelector("#structureResult");
    structureResult.replaceChildren();
    Object.entries(data.structure || {}).forEach(([section, found]) => {
        const row = document.createElement("div");
        row.className = "structure-item";

        const label = document.createElement("span");
        label.textContent = section;

        const result = document.createElement("strong");
        result.className = found ? "found" : "missing";
        result.textContent = found ? "Found" : "Missing";

        row.append(label, result);
        structureResult.appendChild(row);
    });

    document.querySelector(".score-status p").textContent =
        `${data.words ?? 0} words across ${data.pages ?? 0} page(s).`;
    const scoreStamp = document.querySelector("#scoreStamp");
    scoreStamp.classList.remove("stamping");
    requestAnimationFrame(() => scoreStamp.classList.add("stamping"));
}

function renderList(selector, items) {
    const list = document.querySelector(selector);
    list.replaceChildren();

    (items.length ? items : ["None identified."]).forEach((item) => {
        const entry = document.createElement("li");
        entry.textContent = item;
        list.appendChild(entry);
    });
}