document.addEventListener('DOMContentLoaded', function() {
    const urlForm = document.getElementById('urlForm');
    if (urlForm) {
        urlForm.addEventListener('submit', function(e) {
            this.classList.add('loading');
        });
    }
});