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
    
    fetchUserInfo();
    
    showSection('inventory'); 
}

function showSection(sectionId) {
    document.querySelectorAll('main section').forEach(sec => sec.classList.add('hidden'));
    document.getElementById(`section-${sectionId}`).classList.remove('hidden');
    if (sectionId === 'inventory') fetchStockLevels();
    if (sectionId === 'products') fetchProducts();
    if (sectionId === 'orders') fetchOrders();
    if (sectionId === 'finances') { 
        fetchFinances();
        fetchOverheadExpenses();
    }
    if (sectionId === 'transactions') fetchTransactionHistory();
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
        // 1. Fetch the master product catalog (Recipes)
        const prodRes = await fetch(`${API_URL}/products/list`, { headers: getHeaders() });
        if (prodRes.status === 401) return logout();
        const products = await prodRes.json();

        // 2. Fetch the active Finished Goods (Baked Inventory)
        const invRes = await fetch(`${API_URL}/production/finished-inventory`, { headers: getHeaders() });
        const finishedGoods = await invRes.json();

        // 3. Group the baked inventory by product ID so we know how many of each are on the counter
        const stockMap = {};
        finishedGoods.forEach(fg => {
            stockMap[fg.product_id] = (stockMap[fg.product_id] || 0) + fg.quantity_remaining;
        });
        
        const grid = document.getElementById('products-grid');
        grid.innerHTML = products.map(p => {
            const bakedStock = stockMap[p.id] || 0;
            const canSell = bakedStock > 0;

            return `
                <div class="bg-white p-4 rounded shadow border border-gray-100 flex flex-col justify-between">
                    <div>
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs text-gray-400">ID: #${p.id}</span>
                            <span class="px-2 py-1 ${canSell ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'} text-xs rounded-full font-bold border ${canSell ? 'border-green-200' : 'border-red-200'}">
                                🥯 Baked Stock: ${bakedStock}
                            </span>
                        </div>
                        <h3 class="font-bold text-lg text-indigo-700">${p.name}</h3>
                        <p class="text-2xl mt-1 mb-4 font-light">$${p.retail_price.toFixed(2)}</p>
                    </div>

                    <div class="space-y-3 pt-4 border-t border-gray-100">
                        <div class="flex space-x-2">
                            <input type="number" id="bake-qty-${p.id}" placeholder="Qty" class="w-1/3 p-2 border rounded text-sm bg-gray-50" min="1" value="10">
                            <button onclick="bakeProduct(${p.id})" class="w-2/3 bg-indigo-500 text-white p-2 rounded hover:bg-indigo-600 transition font-bold text-sm">
                                👨‍🍳 Bake Batch
                            </button>
                        </div>
                        
                        <button onclick="recordSale(${p.id}, ${p.retail_price})" 
                            class="w-full ${canSell ? 'bg-green-500 hover:bg-green-600' : 'bg-gray-300 cursor-not-allowed'} text-white p-3 rounded transition font-bold text-lg shadow-sm" 
                            ${canSell ? '' : 'disabled'}>
                            🛒 Sell 1 Item
                        </button>
                        <button onclick="logWaste(${p.id})" class="text-xs bg-orange-100 text-orange-800 p-1 rounded border border-orange-200 mt-2">
                            🗑️ Mark Waste
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) { console.error("Error loading products/inventory:", err); }
}

async function bakeProduct(productId) {
    const qtyInput = document.getElementById(`bake-qty-${productId}`);
    const qty = parseInt(qtyInput.value);
    
    if (!qty || qty <= 0) {
        alert("Please enter a valid quantity to bake.");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/production/run`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ product_id: productId, quantity_produced: qty })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to bake product.");
        }

        alert(`Successfully baked ${qty} items! Raw ingredients have been deducted.`);
        
        // Refresh views to show the new baked stock and lower raw ingredient stock
        fetchProducts(); 
        fetchStockLevels(); 

    } catch (err) {
        alert(`Baking Error: ${err.message}`);
    }
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

        alertBox.className = 'mb-4 p-4 rounded text-white font-bold bg-green-500 block shadow';
        alertBox.innerHTML = `✅ Sale Recorded! Rev: $${data.sale_price.toFixed(2)} | FIFO Margin: $${data.margin_fifo.toFixed(2)}`;
        
        // Refresh the POS grid so the "Baked Stock" badge decrements instantly
        fetchProducts(); 

    } catch (err) {
        alertBox.className = 'mb-4 p-4 rounded text-white font-bold bg-red-500 block shadow';
        alertBox.textContent = `❌ Sale Failed: ${err.detail || "Error processing transaction"}`;
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

async function logWaste(lotId) {
    const qty = prompt("How many items are being wasted?");
    const reason = prompt("Reason (e.g., Expired, Dropped, Stale)?");

    if (!qty || isNaN(qty)) return;

    try {
        const res = await fetch(`${API_URL}/production/log-waste?lot_id=${lotId}&qty=${qty}&reason=${reason}`, {
            method: 'POST',
            headers: getHeaders()
        });

        if (!res.ok) throw await res.json();

        alert("Waste recorded successfully!");
        fetchProducts(); // Refresh the POS display
    } catch (err) {
        alert("Error: " + (err.detail || "Could not log waste"));
    }
}

async function fetchFinances() {
    try {
        const res = await fetch(`${API_URL}/sales/financial-summary`, { 
            headers: getHeaders() 
        });
        
        if (!res.ok) throw await res.json();
        const data = await res.json();
        
        // Log to console so you can see it working in real-time
        console.log("Updating Dashboard UI with:", data);

        // Update the actual text on the screen
        document.getElementById('finance-revenue').textContent = `$${data.total_revenue.toFixed(2)}`;
        document.getElementById('finance-waste').textContent = `-$${data.total_waste_loss.toFixed(2)}`;
        document.getElementById('finance-profit').textContent = `$${data.net_profit.toFixed(2)}`;
        
        // Line to show overhead deduction
        if (document.getElementById('finance-overhead')) {
            document.getElementById('finance-overhead').textContent = `-$${data.total_overhead.toFixed(2)}`;
        }

    } catch (err) {
        console.error("Finance UI Update failed:", err);
    }
}

async function fetchTransactionHistory() {
    try {
        const res = await fetch(`${API_URL}/sales/history`, { headers: getHeaders() });
        const logs = await res.json();
        
        const tbody = document.getElementById('transactions-table-body');
        tbody.innerHTML = logs.map(log => `
            <tr class="hover:bg-gray-50">
                <td class="p-3 border-b text-gray-500">${new Date(log.timestamp).toLocaleString()}</td>
                <td class="p-3 border-b font-medium text-indigo-700">${log.product_name}</td>
                <td class="p-3 border-b text-green-600 font-bold">$${log.sale_price.toFixed(2)}</td>
                <td class="p-3 border-b text-indigo-600">$${log.margin_fifo.toFixed(2)}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error("Failed to load transactions", err);
    }
}

async function fetchOverheadExpenses() {
    try {
        const res = await fetch(`${API_URL}/sales/overhead`, { headers: getHeaders() });
        const expenses = await res.json();
        
        const tbody = document.getElementById('overhead-table-body');
        tbody.innerHTML = expenses.map(exp => `
            <tr class="hover:bg-gray-50 border-b">
                <td class="p-3 font-medium">${exp.name}</td>
                <td class="p-3 font-bold text-red-600">$${exp.monthly_amount.toFixed(2)}</td>
                <td class="p-3"><span class="bg-gray-100 px-2 py-1 rounded text-xs text-gray-600 uppercase font-bold">${exp.category}</span></td>
                <td class="p-3 text-right space-x-2">
                    <button onclick="deleteExpense(${exp.id})" class="text-red-500 hover:text-red-700 text-xs font-bold">Delete</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error("Failed to load overhead:", err);
    }
}

async function openAddExpenseModal() {
    const name = prompt("Expense Name (e.g., Kitchen Rent):");
    const amount = prompt("Monthly Amount ($):");
    const category = prompt("Category (Fixed, Subscription, Utility):");

    if (!name || !amount || isNaN(amount)) return;

    try {
        const res = await fetch(`${API_URL}/sales/overhead`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ name, monthly_amount: parseFloat(amount), category })
        });
        
        if (!res.ok) throw await res.json();
        alert("Overhead expense added!");
        fetchOverheadExpenses();
        fetchFinances(); // Refresh total net profit
    } catch (err) {
        alert("Error: " + (err.detail || "Failed to add expense"));
    }
}

async function deleteExpense(id) {
    if (!confirm("Remove this expense?")) return;
    try {
        const res = await fetch(`${API_URL}/sales/overhead/${id}`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        if (res.ok) {
            fetchOverheadExpenses();
            fetchFinances();
        }
    } catch (err) {
        console.error("Delete failed:", err);
    }
}