import '../css/notifications.css';

export function markRead(id, csrfToken) {
    return fetch(`/admin/notifications/${id}/read/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken }
    }).then(r => r.json());
}

export function readAll(csrfToken) {
    return fetch('/admin/notifications/read-all/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken }
    }).then(r => r.json());
}

// Expose to window for traditional onclick handlers
window.markRead = (id) => {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    markRead(id, csrfToken).then(data => {
        if(data.status === 'success') {
            const item = document.getElementById(`n-${id}`);
            if(item) {
                item.classList.remove('unread');
                item.querySelector('.ph-check')?.parentElement.remove();
            }
        }
    });
};

window.readAll = () => {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    readAll(csrfToken).then(data => {
        if(data.status === 'success') {
            document.querySelectorAll('.notification-item').forEach(el => el.classList.remove('unread'));
            document.querySelectorAll('.notification-item .ph-check').forEach(i => i.parentElement.remove());
        }
    });
};
