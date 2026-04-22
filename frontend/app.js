// app.js
const API_URL = 'http://localhost:8100';

// --- INIT & AUTH ---
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('bakery_token');
    if (token) showDashboard();
    
    // Add initial blank rows to dynamic forms
    addRecipeRow();
    addOrderItemRow();
});

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new URLSearchParams();
    formData.append('username', document.getElementById('username').value);
    formData.append('password', document.getElementById('password').value);

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });

        if (!response.ok) throw new Error("Invalid credentials");
        const data = await response.json();
        localStorage.setItem('bakery_token', data.access_token);
        
        document.getElementById('login-error').classList.add('hidden');
        showDashboard();
    } catch (err) {
        const errorEl = document.getElementById('login-error');
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
    }
});

function logout() {
    localStorage.removeItem('bakery_token');
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('login-view').classList.remove('hidden');
    document.getElementById('login-view').classList.add('flex');
}

function getHeaders() {
    return {
        'Authorization': `Bearer ${localStorage.getItem('bakery_token')}`,
        'Content-Type': 'application/json'
    };
}

// --- NAVIGATION ---
function showDashboard() {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('login-view').classList.remove('flex');
    document.getElementById('dashboard-view').classList.remove('hidden');
    
    fetchUserInfo(); // <--- ADD THIS LINE HERE
    
    showSection('inventory'); 
}

function showSection(sectionId) {
    document.querySelectorAll('main section').forEach(sec => sec.classList.add('hidden'));
    document.getElementById(`section-${sectionId}`).classList.remove('hidden');
    if (sectionId === 'inventory') fetchStockLevels();
    if (sectionId === 'products') fetchProducts();
    if (sectionId === 'orders') fetchOrders();
}

async function fetchUserInfo() {
    try {
        const res = await fetch(`${API_URL}/users/me`, { headers: getHeaders() });
        if (!res.ok) return; // Fail silently if something goes wrong
        
        const data = await res.json();
        
        // Inject the bakery name and user info into the sidebar
        document.getElementById('bakery-name-display').textContent = data.business_name;
        document.getElementById('user-role-display').textContent = `User: ${data.username} (${data.role})`;
    } catch (err) {
        console.error("Failed to fetch user info:", err);
    }
}

// ==========================================
// 1. INVENTORY SYSTEM
// ==========================================

// Add Master Ingredient
document.getElementById('add-ingredient-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('new-ing-name').value;
    const base_unit = document.getElementById('new-ing-unit').value;

    try {
        const res = await fetch(`${API_URL}/inventory/add-ingredient`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ name, base_unit, is_non_food: false })
        });
        if (!res.ok) throw await res.json();
        alert("Ingredient added!");
        e.target.reset();
        fetchStockLevels();
    } catch (err) {
        alert(err.detail || "Failed to add ingredient");
    }
});

// Receive Stock Lot
document.getElementById('receive-stock-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('recv-id').value;
    const qty = document.getElementById('recv-qty').value;
    const unit = document.getElementById('recv-unit').value;
    const cost = document.getElementById('recv-cost').value;

    try {
        const res = await fetch(`${API_URL}/inventory/receive-lot?ingredient_id=${id}&qty=${qty}&unit=${unit}&cost=${cost}`, {
            method: 'POST',
            headers: getHeaders()
        });
        if (!res.ok) throw await res.json();
        alert("Stock received!");
        e.target.reset();
        fetchStockLevels();
    } catch (err) {
        alert(err.detail || "Failed to receive stock");
    }
});

async function fetchStockLevels() {
    try {
        const res = await fetch(`${API_URL}/inventory/stock-levels`, { headers: getHeaders() });
        if (res.status === 401) return logout(); 
        const stock = await res.json();
        
        const tbody = document.getElementById('inventory-table-body');
        tbody.innerHTML = stock.map(item => `
            <tr>
                <td class="p-2 border-b text-gray-500">#${item.ingredient_id}</td>
                <td class="p-2 border-b font-medium">${item.name}</td>
                <td class="p-2 border-b">${item.total_quantity.toFixed(2)}</td>
                <td class="p-2 border-b text-gray-500">${item.base_unit}</td>
                <td class="p-2 border-b text-right space-x-2">
                    <button onclick="editIngredient(${item.ingredient_id}, '${item.name}', '${item.base_unit}')" class="text-blue-500 hover:text-blue-700 font-bold">Edit</button>
                    <button onclick="deleteIngredient(${item.ingredient_id})" class="text-red-500 hover:text-red-700 font-bold">Delete</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

async function editIngredient(id, currentName, currentUnit) {
    // Prompt the user for the new details (pre-filled with current ones)
    const newName = prompt("Update Ingredient Name:", currentName);
    if (!newName) return; // User cancelled
    
    const newUnit = prompt("Update Base Unit (e.g. grams, ml):", currentUnit);
    if (!newUnit) return; // User cancelled

    try {
        const res = await fetch(`${API_URL}/inventory/edit-ingredient/${id}`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({ name: newName, base_unit: newUnit, is_non_food: false })
        });
        
        if (!res.ok) throw await res.json();
        
        alert("Ingredient updated successfully!");
        fetchStockLevels(); // Refresh the table
    } catch (err) {
        alert(err.detail || "Failed to update ingredient");
    }
}

async function deleteIngredient(id) {
    // Confirm before deleting
    if (!confirm("Are you sure you want to delete this ingredient? This will fail if it is used in active recipes or stock lots.")) return;

    try {
        const res = await fetch(`${API_URL}/inventory/remove-ingredient/${id}`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        
        if (!res.ok) throw await res.json();
        
        alert("Ingredient deleted successfully!");
        fetchStockLevels(); // Refresh the table
    } catch (err) {
        alert(err.detail || "Failed to delete ingredient");
    }
}
async function editIngredient(id, currentName, currentUnit) {
    // Prompt the user for the new details (pre-filled with current ones)
    const newName = prompt("Update Ingredient Name:", currentName);
    if (!newName) return; // User cancelled
    
    const newUnit = prompt("Update Base Unit (e.g. grams, ml):", currentUnit);
    if (!newUnit) return; // User cancelled

    try {
        const res = await fetch(`${API_URL}/inventory/edit-ingredient/${id}`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({ name: newName, base_unit: newUnit, is_non_food: false })
        });
        
        if (!res.ok) throw await res.json();
        
        alert("Ingredient updated successfully!");
        fetchStockLevels(); // Refresh the table
    } catch (err) {
        alert(err.detail || "Failed to update ingredient");
    }
}

async function deleteIngredient(id) {
    // Confirm before deleting
    if (!confirm("Are you sure you want to delete this ingredient? This will fail if it is used in active recipes or stock lots.")) return;

    try {
        const res = await fetch(`${API_URL}/inventory/remove-ingredient/${id}`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        
        if (!res.ok) throw await res.json();
        
        alert("Ingredient deleted successfully!");
        fetchStockLevels(); // Refresh the table
    } catch (err) {
        alert(err.detail || "Failed to delete ingredient");
    }
}

// ==========================================
// 2. PRODUCTS & RECIPES
// ==========================================

function addRecipeRow() {
    const container = document.getElementById('recipe-rows');
    const row = document.createElement('div');
    row.className = 'flex space-x-2 recipe-row';
    row.innerHTML = `
        <input type="number" placeholder="Ing. ID" class="w-1/2 p-1 border rounded text-sm ing-id" required>
        <input type="number" step="0.01" placeholder="Qty Needed" class="w-1/2 p-1 border rounded text-sm ing-qty" required>
        <button type="button" onclick="this.parentElement.remove()" class="text-red-500 font-bold px-2">X</button>
    `;
    container.appendChild(row);
}

document.getElementById('add-product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('prod-name').value;
    const price = document.getElementById('prod-price').value;
    
    // Parse dynamic rows
    const recipe = [];
    document.querySelectorAll('.recipe-row').forEach(row => {
        const ingId = row.querySelector('.ing-id').value;
        const qty = row.querySelector('.ing-qty').value;
        if(ingId && qty) {
            recipe.push({ ingredient_id: parseInt(ingId), quantity_required: parseFloat(qty) });
        }
    });

    try {
        const res = await fetch(`${API_URL}/products/`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ name, retail_price: parseFloat(price), recipe })
        });
        if (!res.ok) throw await res.json();
        alert("Product and Recipe saved!");
        e.target.reset();
        document.getElementById('recipe-rows').innerHTML = '';
        addRecipeRow();
        fetchProducts();
    } catch (err) {
        alert(err.detail || "Failed to save product");
    }
});

async function fetchProducts() {
    try {
        const res = await fetch(`${API_URL}/products/list`, { headers: getHeaders() });
        if (res.status === 401) return logout();
        const products = await res.json();
        
        const grid = document.getElementById('products-grid');
        grid.innerHTML = products.map(p => `
            <div class="bg-white p-4 rounded shadow border border-gray-100 flex flex-col justify-between">
                <div>
                    <span class="text-xs text-gray-400">ID: #${p.id}</span>
                    <h3 class="font-bold text-lg text-indigo-700">${p.name}</h3>
                    <p class="text-2xl mt-2 mb-4 font-light">$${p.retail_price.toFixed(2)}</p>
                </div>
                <button onclick="recordSale(${p.id}, ${p.retail_price})" class="w-full bg-green-500 text-white p-2 rounded hover:bg-green-600 transition font-bold">
                    Sell 1 Item
                </button>
            </div>
        `).join('');
    } catch (err) { console.error(err); }
}

async function recordSale(productId, price) {
    const alertBox = document.getElementById('sale-alert');
    try {
        const res = await fetch(`${API_URL}/sales/record-sale`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ item_id: productId, quantity: 1, price: price })
        });
        const data = await res.json();
        if (!res.ok) throw data;

        alertBox.className = 'mb-4 p-4 rounded text-white font-bold bg-green-500 block';
        alertBox.innerHTML = `Sale Recorded! Rev: $${data.sale_price.toFixed(2)} | FIFO Margin: $${data.margin_fifo.toFixed(2)}`;
    } catch (err) {
        alertBox.className = 'mb-4 p-4 rounded text-white font-bold bg-red-500 block';
        alertBox.textContent = `Sale Failed: ${err.detail || "Error"}`;
    }
}

// ==========================================
// 3. CUSTOM ORDERS
// ==========================================

function addOrderItemRow() {
    const container = document.getElementById('order-item-rows');
    const row = document.createElement('div');
    row.className = 'flex space-x-2 order-row';
    row.innerHTML = `
        <input type="number" placeholder="Prod. ID" class="w-1/2 p-1 border rounded text-sm ord-id" required>
        <input type="number" placeholder="Qty" class="w-1/4 p-1 border rounded text-sm ord-qty" required>
        <button type="button" onclick="this.parentElement.remove()" class="text-red-500 font-bold px-2">X</button>
    `;
    container.appendChild(row);
}

document.getElementById('add-order-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Convert local datetime to ISO standard for FastAPI
    const rawDate = document.getElementById('order-date').value;
    const isoDate = new Date(rawDate).toISOString();

    const payload = {
        customer_name: document.getElementById('order-customer').value,
        description: document.getElementById('order-desc').value,
        delivery_date: isoDate,
        items: []
    };

    document.querySelectorAll('.order-row').forEach(row => {
        const pId = row.querySelector('.ord-id').value;
        const qty = row.querySelector('.ord-qty').value;
        if(pId && qty) {
            payload.items.push({ product_id: parseInt(pId), quantity: parseInt(qty) });
        }
    });

    try {
        const res = await fetch(`${API_URL}/orders/request-quote`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw await res.json();
        alert("Order Quote Drafted!");
        e.target.reset();
        document.getElementById('order-item-rows').innerHTML = '';
        addOrderItemRow();
        fetchOrders();
    } catch (err) {
        alert(err.detail || "Failed to create order");
    }
});

async function fetchOrders() {
    try {
        const res = await fetch(`${API_URL}/orders/pipeline`, { headers: getHeaders() });
        if (res.status === 401) return logout();
        const orders = await res.json();
        
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = orders.map(order => `
            <tr>
                <td class="p-2 border-b font-medium">#${order.id}</td>
                <td class="p-2 border-b">${order.customer_name}</td>
                <td class="p-2 border-b">${new Date(order.delivery_date).toLocaleDateString()}</td>
                <td class="p-2 border-b">
                    <span class="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full font-bold">
                        ${order.status}
                    </span>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}