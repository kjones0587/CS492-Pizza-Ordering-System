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
    // Top Navbar Cart Badge & Toast Notification Helpers (Task T1-03: Kellen Jones)
    // -------------------------------------------------------------------------
    const navCartBadge = document.getElementById('nav-cart-badge');
    const cartToastEl = document.getElementById('cart-toast');
    let cartToastInstance = null;
    if (cartToastEl && typeof bootstrap !== 'undefined' && bootstrap.Toast) {
        cartToastInstance = new bootstrap.Toast(cartToastEl, { delay: 4500 });
    }

    function showCartToast(data) {
        if (!cartToastEl || !cartToastInstance) return;
        const titleEl = document.getElementById('cart-toast-title');
        const msgEl = document.getElementById('cart-toast-message');
        const subtotalEl = document.getElementById('cart-toast-subtotal');
        const viewCartBtn = document.getElementById('cart-toast-view-btn');
        const iconWrapper = document.getElementById('cart-toast-icon-wrapper');
        const iconEl = document.getElementById('cart-toast-icon');

        const toastFooter = document.getElementById('cart-toast-footer');

        const title = data.title || 'Added to Cart!';
        const qty = data.quantity || 1;
        const name = data.item_name || 'Item';
        const message = data.message || `${qty}x ${name} added to your order.`;

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;

        if (iconEl) {
            iconEl.className = data.icon || 'bi bi-cart-check-fill fs-5';
        }

        if (iconWrapper) {
            iconWrapper.className = `rounded-circle p-2 d-flex align-items-center justify-content-center me-3 flex-shrink-0 text-white ${data.iconBg || 'bg-success'}`;
        }

        let hasFooterContent = false;
        if (subtotalEl) {
            if (data.cart_subtotal !== undefined) {
                subtotalEl.textContent = `Cart Subtotal: $${data.cart_subtotal.toFixed(2)}`;
                subtotalEl.style.display = 'inline';
                hasFooterContent = true;
            } else {
                subtotalEl.style.display = 'none';
            }
        }

        // Contextually hide "View Cart" button if customer is already viewing /cart
        if (viewCartBtn) {
            if (window.location.pathname.startsWith('/cart')) {
                viewCartBtn.style.display = 'none';
            } else {
                viewCartBtn.style.display = 'inline-flex';
                hasFooterContent = true;
            }
        }

        if (toastFooter) {
            toastFooter.style.display = hasFooterContent ? 'flex' : 'none';
        }

        cartToastInstance.show();
    }

    function triggerCartBadgePop(count) {
        if (!navCartBadge) return;
        navCartBadge.textContent = count;
        if (count > 0) {
            navCartBadge.classList.remove('d-none');
            navCartBadge.classList.remove('badge-bounce');
            // Force browser reflow to restart CSS keyframe animation
            void navCartBadge.offsetWidth;
            navCartBadge.classList.add('badge-bounce');
        } else {
            navCartBadge.classList.add('d-none');
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
        const modalToppingsSection = document.getElementById('modal-toppings-section');
        const modalToppingsContainer = document.getElementById('modal-toppings-container');
        const toppingsCountBadge = document.getElementById('toppings-selected-count');
        const modalNotesInput = document.getElementById('modal-notes');
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
            const checkedToppings = modalToppingsContainer ? modalToppingsContainer.querySelectorAll('input[name="toppings"]:checked') : [];
            let toppingsCount = 0;
            checkedToppings.forEach(top => {
                toppingsCount++;
                if (top.dataset.modifier) {
                    price += parseFloat(top.dataset.modifier);
                }
            });
            if (toppingsCountBadge) {
                toppingsCountBadge.textContent = `${toppingsCount} selected`;
                if (toppingsCount > 0) {
                    toppingsCountBadge.className = 'badge bg-danger text-white border-0 fw-medium';
                } else {
                    toppingsCountBadge.className = 'badge bg-light text-secondary border fw-normal';
                }
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
                        if (modalNotesInput) modalNotesInput.value = '';

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

                        // Render Toppings (Tasks T1-03 / T1-04)
                        if (modalToppingsContainer) modalToppingsContainer.innerHTML = '';
                        if (item.options && item.options.toppings && item.options.toppings.length > 0) {
                            if (modalToppingsSection) modalToppingsSection.style.display = 'block';
                            if (toppingsCountBadge) {
                                toppingsCountBadge.textContent = '0 selected';
                                toppingsCountBadge.className = 'badge bg-light text-secondary border fw-normal';
                            }
                            item.options.toppings.forEach((top, idx) => {
                                const modVal = top.price_modifier || 0.0;
                                const modText = modVal > 0 ? `+$${modVal.toFixed(2)}` : 'Free';
                                const catBadge = top.category === 'Meats' ? 'bg-danger-subtle text-danger' :
                                                 top.category === 'Cheese' ? 'bg-warning-subtle text-dark' : 'bg-success-subtle text-success';
                                modalToppingsContainer.innerHTML += `
                                    <div class="col-sm-6">
                                        <label class="d-flex align-items-center justify-content-between p-2 rounded-3 border bg-white topping-card-label mb-0 w-100" for="topping_${idx}" style="cursor: pointer;">
                                            <div class="d-flex align-items-center">
                                                <input class="form-check-input me-2 mt-0" type="checkbox" name="toppings" id="topping_${idx}" value="${top.name}" data-modifier="${modVal}">
                                                <span class="small fw-semibold text-dark">${top.name}</span>
                                            </div>
                                            <span class="badge ${catBadge} small fw-bold ms-1">${modText}</span>
                                        </label>
                                    </div>
                                `;
                            });
                        } else {
                            if (modalToppingsSection) modalToppingsSection.style.display = 'none';
                        }

                        // Attach listeners to options
                        modalSizesContainer.querySelectorAll('input').forEach(r => r.addEventListener('change', recalcModalPrice));
                        modalCrustsContainer.querySelectorAll('input').forEach(r => r.addEventListener('change', recalcModalPrice));
                        if (modalToppingsContainer) {
                            modalToppingsContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.addEventListener('change', recalcModalPrice));
                        }

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

        // Intercept Customize Modal Form Submit for Zero-Page-Reload Add-to-Cart
        if (modalForm) {
            modalForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const submitBtn = modalForm.querySelector('button[type="submit"]');
                const origBtnHtml = submitBtn ? submitBtn.innerHTML : '';
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Adding...';
                }

                const formData = new FormData(modalForm);

                fetch(modalForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(res => {
                    if (!res.ok) {
                        return res.json().then(errData => {
                            throw new Error(errData.message || 'Failed to add item to cart.');
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.success) {
                        customizeModal.hide();
                        triggerCartBadgePop(data.cart_count);
                        showCartToast(data);

                        // If user happens to be on the /cart page, reload to show new item in list
                        if (window.location.pathname === '/cart' || window.location.pathname === '/cart/') {
                            window.location.reload();
                        }
                    }
                })
                .catch(err => {
                    console.error('AJAX add-to-cart error:', err);
                    alert(err.message || 'Unable to add item to cart. Please try again.');
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = origBtnHtml;
                    }
                });
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

    function updateCartSummary(totals) {
        if (summaryItemCount) summaryItemCount.textContent = totals.item_count;
        if (summarySubtotal) summarySubtotal.textContent = '$' + totals.subtotal.toFixed(2);
        if (summaryTax) summaryTax.textContent = '$' + totals.tax_amount.toFixed(2);

        // Synchronize top navbar cart badge with bounce feedback
        triggerCartBadgePop(totals.item_count);

        // Update catering early-warning banner in cart summary (Task T1-03 / T1-04)
        const cateringBanner = document.getElementById('cart-catering-banner');
        const cateringCount = document.getElementById('cart-catering-count');
        if (cateringBanner && totals.estimates) {
            if (totals.estimates.is_catering) {
                if (cateringCount) cateringCount.textContent = totals.item_count;
                cateringBanner.classList.remove('d-none');
            } else {
                cateringBanner.classList.add('d-none');
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
                return;
            }

            // Intercept inline special instructions update form submission (Task T1-03)
            const noteForm = e.target.closest('.cart-inline-note-form');
            if (noteForm) {
                e.preventDefault();
                const container = noteForm.closest('.cart-note-container');
                const row = noteForm.closest('.cart-row');
                const saveBtn = noteForm.querySelector('button[type="submit"]');
                const origBtnText = saveBtn ? saveBtn.textContent : 'Save';
                if (saveBtn) {
                    saveBtn.disabled = true;
                    saveBtn.textContent = '...';
                }

                const formData = new FormData(noteForm);

                fetch(noteForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const displayEl = container.querySelector('.cart-note-display');
                        const addActionEl = container.querySelector('.cart-add-note-action');
                        const formEl = container.querySelector('.cart-note-form');
                        const textSpan = container.querySelector('.cart-note-text');
                        const inputEl = container.querySelector('.cart-note-input');

                        if (formEl) formEl.classList.add('d-none');

                        if (data.special_notes && data.special_notes.trim().length > 0) {
                            if (textSpan) textSpan.textContent = data.special_notes;
                            if (displayEl) displayEl.classList.remove('d-none');
                            if (addActionEl) addActionEl.classList.add('d-none');
                            if (inputEl) inputEl.value = data.special_notes;
                        } else {
                            if (textSpan) textSpan.textContent = '';
                            if (displayEl) displayEl.classList.add('d-none');
                            if (addActionEl) addActionEl.classList.remove('d-none');
                            if (inputEl) inputEl.value = '';
                        }

                        // Show contextual toast notification
                        const itemName = row ? (row.querySelector('h6')?.textContent?.trim() || 'Item') : 'Item';
                        const hasNote = data.special_notes && data.special_notes.trim().length > 0;
                        showCartToast({
                            title: hasNote ? 'Special Note Updated!' : 'Note Removed',
                            item_name: itemName,
                            message: hasNote ? `"${data.special_notes}" saved for ${itemName}.` : `Special instructions removed for ${itemName}.`,
                            icon: hasNote ? 'bi bi-chat-left-text-fill fs-5' : 'bi bi-dash-circle fs-5',
                            iconBg: hasNote ? 'bg-primary' : 'bg-secondary'
                        });
                    }
                })
                .catch(err => {
                    console.error('Error updating special instructions:', err);
                    noteForm.submit(); // Graceful fallback
                })
                .finally(() => {
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.textContent = origBtnText;
                    }
                });
            }
        });

        // Intercept inline note editing toggle (Edit / Add / Cancel)
        cartTableBody.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.btn-edit-note');
            if (editBtn) {
                const container = editBtn.closest('.cart-note-container');
                if (container) {
                    const displayEl = container.querySelector('.cart-note-display');
                    const addActionEl = container.querySelector('.cart-add-note-action');
                    const formEl = container.querySelector('.cart-note-form');
                    const inputEl = container.querySelector('.cart-note-input');
                    if (displayEl) displayEl.classList.add('d-none');
                    if (addActionEl) addActionEl.classList.add('d-none');
                    if (formEl) formEl.classList.remove('d-none');
                    if (inputEl) {
                        inputEl.focus();
                        inputEl.select();
                    }
                }
                return;
            }

            const cancelBtn = e.target.closest('.btn-cancel-note');
            if (cancelBtn) {
                const container = cancelBtn.closest('.cart-note-container');
                if (container) {
                    const displayEl = container.querySelector('.cart-note-display');
                    const addActionEl = container.querySelector('.cart-add-note-action');
                    const formEl = container.querySelector('.cart-note-form');
                    const textSpan = container.querySelector('.cart-note-text');
                    const inputEl = container.querySelector('.cart-note-input');
                    if (formEl) formEl.classList.add('d-none');
                    if (textSpan && textSpan.textContent.trim().length > 0) {
                        if (displayEl) displayEl.classList.remove('d-none');
                        if (inputEl) inputEl.value = textSpan.textContent.trim();
                    } else {
                        if (addActionEl) addActionEl.classList.remove('d-none');
                        if (inputEl) inputEl.value = '';
                    }
                }
            }
        });

        // -------------------------------------------------------------------------
        // In-Cart Pizza Toppings Edit Modal (Task T1-03: Kellen Jones)
        // -------------------------------------------------------------------------
        const editToppingsModalEl = document.getElementById('editToppingsModal');
        if (editToppingsModalEl) {
            const editToppingsModal = new bootstrap.Modal(editToppingsModalEl);
            const editForm = document.getElementById('edit-toppings-form');
            const editIndexInput = document.getElementById('edit-toppings-item-index');
            const editItemName = document.getElementById('edit-modal-item-name');
            const editSizeBadge = document.getElementById('edit-modal-size-badge');
            const editCrustBadge = document.getElementById('edit-modal-crust-badge');
            const editToppingsContainer = document.getElementById('edit-toppings-container');
            const editSelectedCount = document.getElementById('edit-toppings-selected-count');
            const editUnitPriceDisplay = document.getElementById('edit-modal-unit-price');
            const editSaveBtn = document.getElementById('edit-toppings-save-btn');

            let editBaseItemPrice = 0.0;
            let editSizeModifier = 0.0;
            let editCrustModifier = 0.0;
            let activeRow = null;

            function recalcEditToppingsPrice() {
                let unitPrice = editBaseItemPrice + editSizeModifier + editCrustModifier;
                const checkedBoxes = editToppingsContainer ? editToppingsContainer.querySelectorAll('input[name="toppings"]:checked') : [];
                let count = 0;
                checkedBoxes.forEach(cb => {
                    count++;
                    if (cb.dataset.modifier) {
                        unitPrice += parseFloat(cb.dataset.modifier);
                    }
                });
                if (editSelectedCount) {
                    editSelectedCount.textContent = `${count} selected`;
                    editSelectedCount.className = count > 0 ? 'badge bg-danger text-white border-0 fw-medium' : 'badge bg-light text-secondary border fw-normal';
                }
                if (editUnitPriceDisplay) {
                    editUnitPriceDisplay.textContent = '$' + unitPrice.toFixed(2);
                }
            }

            // Click listener for Edit/Add Toppings button in cart table
            cartTableBody.addEventListener('click', (e) => {
                const editToppingsBtn = e.target.closest('.btn-edit-toppings');
                if (!editToppingsBtn) return;

                activeRow = editToppingsBtn.closest('.cart-row');
                if (!activeRow) return;

                const index = activeRow.dataset.index;
                const menuItemId = activeRow.dataset.menuItemId;
                const itemName = activeRow.dataset.itemName || 'Pizza';
                const sizeOption = activeRow.dataset.size || '';
                const crustOption = activeRow.dataset.crust || '';
                let currentToppings = [];
                try {
                    currentToppings = JSON.parse(activeRow.dataset.toppings || '[]');
                } catch(err) {
                    currentToppings = [];
                }

                editIndexInput.value = index;
                editItemName.textContent = `Edit Toppings — ${itemName}`;
                if (editSizeBadge) {
                    editSizeBadge.textContent = sizeOption;
                    editSizeBadge.style.display = sizeOption ? 'inline-block' : 'none';
                }
                if (editCrustBadge) {
                    editCrustBadge.textContent = crustOption;
                    editCrustBadge.style.display = crustOption ? 'inline-block' : 'none';
                }

                if (editToppingsContainer) {
                    editToppingsContainer.innerHTML = '<div class="col-12 text-center py-3 text-muted"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading toppings...</div>';
                }

                editToppingsModal.show();

                fetch(`/menu/item/${menuItemId}`)
                    .then(r => r.json())
                    .then(item => {
                        editBaseItemPrice = item.base_price || 0.0;
                        editSizeModifier = 0.0;
                        editCrustModifier = 0.0;

                        if (item.options && item.options.sizes) {
                            const sizeObj = item.options.sizes.find(s => s.name === sizeOption);
                            if (sizeObj) editSizeModifier = sizeObj.price_modifier || 0.0;
                        }
                        if (item.options && item.options.crusts) {
                            const crustObj = item.options.crusts.find(c => c.name === crustOption);
                            if (crustObj) editCrustModifier = crustObj.price_modifier || 0.0;
                        }

                        if (editToppingsContainer) editToppingsContainer.innerHTML = '';

                        if (item.options && item.options.toppings && item.options.toppings.length > 0) {
                            item.options.toppings.forEach((top, idx) => {
                                const modVal = top.price_modifier || 0.0;
                                const modText = modVal > 0 ? `+$${modVal.toFixed(2)}` : 'Free';
                                const catBadge = top.category === 'Meats' ? 'bg-danger-subtle text-danger' :
                                                 top.category === 'Cheese' ? 'bg-warning-subtle text-dark' : 'bg-success-subtle text-success';
                                const isChecked = currentToppings.includes(top.name) ? 'checked' : '';

                                editToppingsContainer.innerHTML += `
                                    <div class="col-sm-6">
                                        <label class="d-flex align-items-center justify-content-between p-2 rounded-3 border bg-white topping-card-label mb-0 w-100" for="edit_topping_${idx}" style="cursor: pointer;">
                                            <div class="d-flex align-items-center">
                                                <input class="form-check-input me-2 mt-0" type="checkbox" name="toppings" id="edit_topping_${idx}" value="${top.name}" data-modifier="${modVal}" ${isChecked}>
                                                <span class="small fw-semibold text-dark">${top.name}</span>
                                            </div>
                                            <span class="badge ${catBadge} small fw-bold ms-1">${modText}</span>
                                        </label>
                                    </div>
                                `;
                            });

                            editToppingsContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                                cb.addEventListener('change', recalcEditToppingsPrice);
                            });
                        } else {
                            if (editToppingsContainer) {
                                editToppingsContainer.innerHTML = '<div class="col-12 text-center py-3 text-muted">No toppings available for this item.</div>';
                            }
                        }

                        recalcEditToppingsPrice();
                    })
                    .catch(err => {
                        console.error('Error loading item toppings:', err);
                        if (editToppingsContainer) {
                            editToppingsContainer.innerHTML = '<div class="col-12 text-center py-3 text-danger">Failed to load toppings. Please try again.</div>';
                        }
                    });
            });

            // Handle AJAX submission of Edit Toppings form
            if (editForm) {
                editForm.addEventListener('submit', (e) => {
                    e.preventDefault();
                    const origBtnHtml = editSaveBtn ? editSaveBtn.innerHTML : '';
                    if (editSaveBtn) {
                        editSaveBtn.disabled = true;
                        editSaveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Saving...';
                    }

                    const formData = new FormData(editForm);

                    fetch(editForm.action, {
                        method: 'POST',
                        body: formData,
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success && activeRow) {
                            // Update active row data-toppings attribute
                            activeRow.dataset.toppings = JSON.stringify(data.toppings);

                            // Update row unit price & line total
                            const unitPriceEl = activeRow.querySelector('.cart-unit-price');
                            if (unitPriceEl) unitPriceEl.textContent = `$${data.unit_price.toFixed(2)}`;

                            const lineTotalEl = activeRow.querySelector('.cart-row-total');
                            if (lineTotalEl) lineTotalEl.textContent = `$${data.line_total.toFixed(2)}`;

                            // Update toppings display in row
                            const toppingsContainer = activeRow.querySelector('.cart-toppings-container');
                            if (toppingsContainer) {
                                const displayEl = toppingsContainer.querySelector('.cart-toppings-display');
                                const addActionEl = toppingsContainer.querySelector('.cart-add-toppings-action');
                                const textSpan = toppingsContainer.querySelector('.cart-toppings-text');

                                if (data.toppings && data.toppings.length > 0) {
                                    if (textSpan) textSpan.textContent = data.toppings.join(', ');
                                    if (displayEl) displayEl.classList.remove('d-none');
                                    if (addActionEl) addActionEl.classList.add('d-none');
                                } else {
                                    if (textSpan) textSpan.textContent = '';
                                    if (displayEl) displayEl.classList.add('d-none');
                                    if (addActionEl) addActionEl.classList.remove('d-none');
                                }
                            }

                            // Update Order Summary card with recalculations
                            if (data.totals) {
                                updateCartSummary(data.totals);
                            }

                            editToppingsModal.hide();

                            // Show contextual toast notification
                            const hasToppings = data.toppings && data.toppings.length > 0;
                            showCartToast({
                                title: 'Toppings Updated!',
                                item_name: data.item_name,
                                message: hasToppings ? `Toppings updated: ${data.toppings.join(', ')}` : `All extra toppings removed from ${data.item_name}.`,
                                icon: 'bi bi-check-circle-fill fs-5',
                                iconBg: 'bg-primary'
                            });
                        } else {
                            alert(data.message || 'Failed to update toppings.');
                        }
                    })
                    .catch(err => {
                        console.error('Error updating toppings:', err);
                        editForm.submit(); // Graceful fallback
                    })
                    .finally(() => {
                        if (editSaveBtn) {
                            editSaveBtn.disabled = false;
                            editSaveBtn.innerHTML = origBtnHtml;
                        }
                    });
                });
            }
        }
    }
});
