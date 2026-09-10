// =============================================================================
// Task T1-03: Shopping Cart & Order Customization Interactive Logic
// Author / Module Lead: Kellen Jones (Scrum Master & Development Team)
// Description: Provides dynamic client-side bill calculation, options customizer
// modal logic, and zero-page-reload AJAX quantity and removal controls.
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------------------
    // 1. Checkout Dynamic Bill Recalculation (Pickup vs Delivery) - Task T1-04
    // -------------------------------------------------------------------------
    const orderTypeRadios = document.querySelectorAll('input[name="order_type"]');
    const deliveryAddressGroup = document.getElementById('delivery-address-group');
    const deliveryAddressInput = document.getElementById('delivery_address');
    const deliveryFeeRow = document.getElementById('delivery-fee-row');
    const billDeliveryFee = document.getElementById('bill-delivery-fee');
    const billTax = document.getElementById('bill-tax');
    const billTotal = document.getElementById('bill-total');

    function updateOrderTypeView(type) {
        if (!deliveryAddressGroup) return;

        if (type === 'delivery') {
            deliveryAddressGroup.style.display = 'block';
            if (deliveryAddressInput) deliveryAddressInput.required = true;
            if (deliveryFeeRow) deliveryFeeRow.style.display = 'flex';
        } else {
            deliveryAddressGroup.style.display = 'none';
            if (deliveryAddressInput) {
                deliveryAddressInput.required = false;
                deliveryAddressInput.value = '';
            }
            if (deliveryFeeRow) deliveryFeeRow.style.display = 'none';
        }

        // Fetch recalculated totals from server
        fetch('/cart/calculate-api', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ order_type: type })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success && data.totals) {
                if (billDeliveryFee) billDeliveryFee.textContent = '$' + data.totals.delivery_fee.toFixed(2);
                if (billTax) billTax.textContent = '$' + data.totals.tax_amount.toFixed(2);
                if (billTotal) billTotal.textContent = '$' + data.totals.total_amount.toFixed(2);
            }
        })
        .catch(err => console.error('Error updating order totals:', err));
    }

    if (orderTypeRadios.length > 0) {
        orderTypeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                updateOrderTypeView(e.target.value);
            });
        });
        // Initial state sync
        const checkedRadio = document.querySelector('input[name="order_type"]:checked');
        if (checkedRadio) {
            updateOrderTypeView(checkedRadio.value);
        }
    }

    // -------------------------------------------------------------------------
    // 2. Menu Item Customization Modal - Task T1-02 / T1-03
    // -------------------------------------------------------------------------
    const customizeModalEl = document.getElementById('customizeModal');
    if (customizeModalEl) {
        const customizeModal = new bootstrap.Modal(customizeModalEl);
        const modalForm = document.getElementById('customize-form');
        const modalItemName = document.getElementById('modal-item-name');
        const modalItemDesc = document.getElementById('modal-item-desc');
        const modalItemId = document.getElementById('modal-item-id');
        const modalSizesContainer = document.getElementById('modal-sizes-container');
        const modalCrustsContainer = document.getElementById('modal-crusts-container');
        const modalUnitPriceDisplay = document.getElementById('modal-unit-price');
        const modalQtyInput = document.getElementById('modal-quantity');
        let currentBasePrice = 0.0;

        function recalcModalPrice() {
            let price = currentBasePrice;
            const selectedSize = document.querySelector('input[name="size_option"]:checked');
            if (selectedSize && selectedSize.dataset.modifier) {
                price += parseFloat(selectedSize.dataset.modifier);
            }
            const selectedCrust = document.querySelector('input[name="crust_option"]:checked');
            if (selectedCrust && selectedCrust.dataset.modifier) {
                price += parseFloat(selectedCrust.dataset.modifier);
            }
            const qty = parseInt(modalQtyInput.value, 10) || 1;
            modalUnitPriceDisplay.textContent = '$' + (price * qty).toFixed(2);
        }

        document.querySelectorAll('.btn-customize-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const itemId = btn.dataset.itemId;
                fetch(`/menu/item/${itemId}`)
                    .then(r => r.json())
                    .then(item => {
                        modalItemId.value = item.id;
                        modalItemName.textContent = item.name;
                        modalItemDesc.textContent = item.description;
                        currentBasePrice = item.base_price;
                        modalQtyInput.value = 1;

                        // Render Sizes
                        modalSizesContainer.innerHTML = '';
                        if (item.options && item.options.sizes && item.options.sizes.length > 0) {
                            document.getElementById('modal-sizes-section').style.display = 'block';
                            item.options.sizes.forEach((s, idx) => {
                                const modText = s.price_modifier > 0 ? ` (+$${s.price_modifier.toFixed(2)})` : '';
                                const checked = idx === 0 ? 'checked' : '';
                                modalSizesContainer.innerHTML += `
                                    <div class="form-check form-check-inline me-3 mb-2">
                                        <input class="form-check-input" type="radio" name="size_option" id="size_${idx}" value="${s.name}" data-modifier="${s.price_modifier}" ${checked}>
                                        <label class="form-check-label fw-medium" for="size_${idx}">${s.name}${modText}</label>
                                    </div>
                                `;
                            });
                        } else {
                            document.getElementById('modal-sizes-section').style.display = 'none';
                        }

                        // Render Crusts
                        modalCrustsContainer.innerHTML = '';
                        if (item.options && item.options.crusts && item.options.crusts.length > 0) {
                            document.getElementById('modal-crusts-section').style.display = 'block';
                            item.options.crusts.forEach((c, idx) => {
                                const modText = c.price_modifier > 0 ? ` (+$${c.price_modifier.toFixed(2)})` : '';
                                const checked = idx === 0 ? 'checked' : '';
                                modalCrustsContainer.innerHTML += `
                                    <div class="form-check me-3 mb-2">
                                        <input class="form-check-input" type="radio" name="crust_option" id="crust_${idx}" value="${c.name}" data-modifier="${c.price_modifier}" ${checked}>
                                        <label class="form-check-label" for="crust_${idx}">${c.name}${modText}</label>
                                    </div>
                                `;
                            });
                        } else {
                            document.getElementById('modal-crusts-section').style.display = 'none';
                        }

                        // Attach listeners to new radio options
                        modalSizesContainer.querySelectorAll('input').forEach(r => r.addEventListener('change', recalcModalPrice));
                        modalCrustsContainer.querySelectorAll('input').forEach(r => r.addEventListener('change', recalcModalPrice));

                        recalcModalPrice();
                        customizeModal.show();
                    })
                    .catch(err => console.error('Error fetching item details:', err));
            });
        });

        if (modalQtyInput) {
            modalQtyInput.addEventListener('input', recalcModalPrice);
            document.getElementById('modal-qty-plus')?.addEventListener('click', () => {
                modalQtyInput.value = parseInt(modalQtyInput.value || 1) + 1;
                recalcModalPrice();
            });
            document.getElementById('modal-qty-minus')?.addEventListener('click', () => {
                const current = parseInt(modalQtyInput.value || 1);
                if (current > 1) {
                    modalQtyInput.value = current - 1;
                    recalcModalPrice();
                }
            });
        }
    }

    // -------------------------------------------------------------------------
    // 3. Live AJAX Quantity Modifiers & Item Removal (Task T1-03: Kellen Jones)
    // Seamlessly adjusts quantities, recalculates row totals & summary box,
    // and syncs the navbar badge without full-page reloads.
    // -------------------------------------------------------------------------
    const cartTableBody = document.getElementById('cart-table-body');
    const cartContentSection = document.getElementById('cart-content-section');
    const cartEmptySection = document.getElementById('cart-empty-section');
    const clearCartForm = document.getElementById('clear-cart-form');
    const summaryItemCount = document.getElementById('summary-item-count');
    const summarySubtotal = document.getElementById('summary-subtotal');
    const summaryTax = document.getElementById('summary-tax');
    const navCartBadge = document.getElementById('nav-cart-badge');

    function updateCartSummary(totals) {
        if (summaryItemCount) summaryItemCount.textContent = totals.item_count;
        if (summarySubtotal) summarySubtotal.textContent = '$' + totals.subtotal.toFixed(2);
        if (summaryTax) summaryTax.textContent = '$' + totals.tax_amount.toFixed(2);

        // Synchronize top navbar cart badge
        if (navCartBadge) {
            if (totals.item_count > 0) {
                navCartBadge.textContent = totals.item_count;
                navCartBadge.classList.remove('d-none');
            } else {
                navCartBadge.textContent = '0';
                navCartBadge.classList.add('d-none');
            }
        }

        // Toggle empty-cart state dynamically if cart has 0 items
        if (totals.item_count === 0) {
            if (cartContentSection) cartContentSection.classList.add('d-none');
            if (clearCartForm) clearCartForm.classList.add('d-none');
            if (cartEmptySection) cartEmptySection.classList.remove('d-none');
        }
    }

    function reindexCartRows() {
        const rows = document.querySelectorAll('.cart-row');
        rows.forEach((row, idx) => {
            row.dataset.index = idx;
            row.querySelectorAll('.cart-input-index').forEach(input => {
                input.value = idx;
            });
            // Update remove form action URL index
            const removeForm = row.querySelector('.cart-remove-form');
            if (removeForm) {
                removeForm.action = `/cart/remove/${idx}`;
            }
        });
    }

    if (cartTableBody) {
        // Intercept quantity modifier form submissions (+ and -)
        cartTableBody.addEventListener('submit', (e) => {
            const qtyForm = e.target.closest('.cart-qty-form');
            if (qtyForm) {
                e.preventDefault();
                const formData = new FormData(qtyForm);
                const row = qtyForm.closest('.cart-row');
                const rowIndex = parseInt(row.dataset.index, 10);

                fetch(qtyForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success && data.totals) {
                        updateCartSummary(data.totals);

                        // If quantity reached zero, the item was removed on backend
                        if (rowIndex >= data.cart.length || data.cart[rowIndex] === undefined) {
                            row.remove();
                            reindexCartRows();
                        } else {
                            // Update row quantity display and line total
                            const updatedItem = data.cart[rowIndex];
                            const qtySpan = row.querySelector('.cart-qty-text');
                            const totalCell = row.querySelector('.cart-row-total');
                            if (qtySpan) qtySpan.textContent = updatedItem.quantity;
                            if (totalCell) totalCell.textContent = '$' + updatedItem.line_total.toFixed(2);
                        }
                    }
                })
                .catch(err => {
                    console.error('Error updating cart item quantity:', err);
                    qtyForm.submit(); // Graceful fallback to standard POST
                });
                return;
            }

            // Intercept item removal form submissions (trash icon)
            const removeForm = e.target.closest('.cart-remove-form');
            if (removeForm) {
                e.preventDefault();
                const row = removeForm.closest('.cart-row');

                fetch(removeForm.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success && data.totals) {
                        updateCartSummary(data.totals);
                        row.remove();
                        reindexCartRows();
                    }
                })
                .catch(err => {
                    console.error('Error removing item from cart:', err);
                    removeForm.submit(); // Graceful fallback to standard POST
                });
            }
        });
    }
});
