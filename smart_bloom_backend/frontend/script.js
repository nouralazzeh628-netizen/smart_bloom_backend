const { useState, useEffect } = React;

const API = "http://127.0.0.1:5000";

const token = localStorage.getItem("token");
if (!token) {
    window.location.href = "login.html";
}

/* ---------- AUTH FETCH ---------- */
function authFetch(url, options = {}) {
    const token = localStorage.getItem("token");

    return fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
            ...options.headers
        }
    });
}

/* ---------- SAMPLE FALLBACK DATA ---------- */
const sampleStats = {
    total_orders: 18,
    total_revenue: 423,
    total_customers: 52,
    best_seller: "White Rose",
    low_stock_count: 2
};
const sampleOrders = [
    { order_id: 1, user_id: 1, total_price: 10, status: "Pending", payment_method: "Visa", order_date: "2026" }
];
const sampleFlowers = [
    { flower_id: 1, flower_name: "Rose", price: 10, stock: 5, image_url: "https://placehold.co/150x150/ffb6c1/white?text=Rose", is_active: true }
];
const sampleBouquets = [
    { bouquet_id: 1, name: "Birthday", description: "Nice", price: 30, image_url: "https://placehold.co/150x150/ffb6c1/white?text=Bouquet" }
];

/* ---------- APP ---------- */
function App() {

    const [stats, setStats] = useState(sampleStats);
    const [orders, setOrders] = useState(sampleOrders);
    const [flowers, setFlowers] = useState(sampleFlowers);
    const [bouquets, setBouquets] = useState(sampleBouquets);

    const [modal, setModal] = useState(false);
    const [selectedFlower, setSelectedFlower] = useState(null);
    const [newStock, setNewStock] = useState("");

    /* ---------- FETCH ---------- */
    useEffect(() => {
        fetchDashboardStats();
        fetchOrders();
        fetchFlowers();
        fetchBouquets();
    }, []);

    async function fetchDashboardStats() {
        try {
            const res = await authFetch(`${API}/admin/dashboard/stats`);
            const data = await res.json();
            setStats(data || sampleStats);
        } catch {
            setStats(sampleStats);
        }
    }

    async function fetchOrders() {
        try {
            const res = await authFetch(`${API}/admin/orders`);
            const data = await res.json();
            setOrders(data.orders || data || sampleOrders);
        } catch {
            setOrders(sampleOrders);
        }
    }

    async function fetchFlowers() {
        try {
            const res = await authFetch(`${API}/admin/flowers`);
            const data = await res.json();
            console.log(data);
            // ✅ Fix image URL
            const flowersData = Array.isArray(data) ? data : data.flowers || sampleFlowers;
            const updatedFlowers = flowersData.map(flower => ({
                ...flower,
                image_url: `${API}/files/${flower.image_url}`
            }));

            setFlowers(updatedFlowers);

        } catch (e) {
            console.log(e);

            setFlowers(sampleFlowers);
        }
    }

    async function fetchBouquets() {
        try {
            const res = await authFetch(`${API}/admin/bouquets`);
            const data = await res.json();
            setBouquets(Array.isArray(data) ? data : data.bouquets || sampleBouquets);
        } catch {
            setBouquets(sampleBouquets);
        }
    }

    /* ---------- UPDATE STOCK ---------- */
    async function updateStock() {
        if (!newStock || newStock <= 0) return alert("Invalid stock");

        await authFetch(`${API}/admin/flowers/${selectedFlower}/stock`, {
            method: "PUT",
            body: JSON.stringify({ stock: Number(newStock) })
        });

        setModal(false);
        setNewStock("");
        fetchFlowers();
    }

    /* ---------- UI ---------- */
    return (
        <div className="dashboard">

            {/* Sidebar */}
            <div className="sidebar">
                <h2>🌸 Admin</h2>
                <ul>
                    <li>Dashboard</li>
                    <li>Flowers</li>
                    <li>Orders</li>
                    <li>Bouquets</li>
                </ul>
            </div>

            {/* Main */}
            <div className="main">

                {/* Header */}
                <div className="header">
                    <h1>Dashboard</h1>
                    <input className="search" placeholder="Search..." />
                </div>

                {/* Cards */}
                <div className="cards">
                    <div className="card">Orders: {stats.total_orders}</div>
                    <div className="card">Revenue: ${stats.total_revenue}</div>
                    <div className="card">Customers: {stats.total_customers}</div>
                    <div className="card">Best Seller: {stats.best_seller}</div>
                    <div className="card">Low Stock: {stats.low_stock_count}</div>
                </div>

                {/* Orders */}
                <h2>Orders</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>User</th>
                            <th>Price</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(orders || []).map(o => (
                            <tr key={o.order_id}>
                                <td>{o.order_id}</td>
                                <td>{o.user_id}</td>
                                <td>${o.total_price}</td>
                                <td className={`status ${(o.status || "").toLowerCase()}`}>
                                    {o.status}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                {/* Flowers */}
                <h2>Flowers</h2>
                <div className="flowers">
                    {(flowers || []).map(f => (
                        <div className="flower" key={f.flower_id}>
                            <img src={f.image_url} alt={f.flower_name} />
                            <h3>{f.flower_name}</h3>
                            <p>${f.price}</p>
                            <p>Stock: {f.stock}</p>
                            <button onClick={() => {
                                setModal(true);
                                setSelectedFlower(f.flower_id);
                            }}>
                                Edit Stock
                            </button>
                        </div>
                    ))}
                </div>

                {/* Bouquets */}
                <h2>Bouquets</h2>
                <div className="flowers">
                    {(bouquets || []).map(b => (
                        <div className="flower" key={b.bouquet_id}>
                            <img src={b.image_url} alt={b.name} />
                            <h3>{b.name}</h3>
                            <p>${b.price}</p>
                        </div>
                    ))}
                </div>

            </div>

            {/* Modal */}
            {modal && (
                <div className="modal">
                    <div className="modal-content">
                        <h3>Update Stock</h3>
                        <input
                            type="number"
                            value={newStock}
                            onChange={(e) => setNewStock(e.target.value)}
                        />
                        <br /><br />
                        <button onClick={updateStock}>Save</button>
                        <button onClick={() => { setModal(false); setNewStock(""); }}>Cancel</button>
                    </div>
                </div>
            )}

        </div>
    );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);