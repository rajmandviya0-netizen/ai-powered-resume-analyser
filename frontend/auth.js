document.addEventListener("DOMContentLoaded", () => {
    updateAccountNavigation();

    document.querySelectorAll("[data-password-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            const isVisible = input.type === "text";
            input.type = isVisible ? "password" : "text";
            button.textContent = isVisible ? "Show" : "Hide";
            button.setAttribute("aria-label", `${isVisible ? "Show" : "Hide"} password`);
            button.setAttribute("aria-pressed", String(!isVisible));
        });
    });

    document.querySelectorAll("[data-auth-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            const feedback = document.querySelector("#authFeedback");
            feedback.classList.remove("is-warning");

            if (!form.reportValidity()) {
                return;
            }

            const isSignup = form.dataset.authForm === "signup";
            if (isSignup) {
                const password = form.elements.password.value;
                const confirmation = form.elements.confirmPassword.value;
                if (password !== confirmation) {
                    feedback.textContent = "Passwords do not match.";
                    feedback.classList.add("is-warning");
                    form.elements.confirmPassword.focus();
                    return;
                }
            }

            const submitButton = form.querySelector("[type='submit']");
            submitButton.disabled = true;
            feedback.textContent = isSignup ? "Creating your account..." : "Signing you in...";

            const payload = {
                email: form.elements.email.value,
                password: form.elements.password.value
            };
            if (isSignup) {
                payload.name = form.elements.name.value;
            }

            try {
                const response = await fetch(`/api/auth/${isSignup ? "signup" : "login"}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || "Authentication failed.");
                }

                feedback.textContent = isSignup ? "Account created. Opening your workspace..." : "Signed in. Opening your workspace...";
                window.location.assign("/");
            } catch (error) {
                feedback.textContent = error.message || "Could not reach the authentication service.";
                feedback.classList.add("is-warning");
                submitButton.disabled = false;
            }
        });
    });
});

async function updateAccountNavigation() {
    const navigation = document.querySelector("#accountLinks");
    if (!navigation) {
        return;
    }

    try {
        const response = await fetch("/api/auth/session");
        if (!response.ok) {
            return;
        }

        const data = await response.json();
        if (!data.authenticated) {
            return;
        }

        navigation.replaceChildren();

        const greeting = document.createElement("span");
        greeting.textContent = `SIGNED IN AS ${data.user.name}`;

        const logoutButton = document.createElement("button");
        logoutButton.type = "button";
        logoutButton.className = "account-link-primary";
        logoutButton.textContent = "Sign out";
        logoutButton.addEventListener("click", async () => {
            await fetch("/api/auth/logout", { method: "POST" });
            window.location.reload();
        });

        navigation.append(greeting, logoutButton);
    } catch {
        // Keep the sign-in links visible if the auth service is unavailable.
    }
}