const API = "http://127.0.0.1:5000";

async function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
        const res = await fetch(`${API}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email,
                password
            })
        });

        const data = await res.json();

        if (!res.ok) {
            document.getElementById("error").innerText = data.error || "Login failed";
            return;
        }

        // ✅ Save token
        localStorage.setItem("token", data.access_token);

        // ✅ Redirect to dashboard
        window.location.href = "index.html";

    } catch (err) {
        document.getElementById("error").innerText = "Server error";
    }
}