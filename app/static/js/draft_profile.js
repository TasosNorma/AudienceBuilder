
document.querySelectorAll('.postBtn').forEach(button => {
    button.addEventListener('click', async function() {
        const post_id = this.getAttribute('post_id');
        if (confirm('Are you sure you want to post a draft?')) {
            try {
                const response = await fetch(`/draft/${post_id}/post`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.csrfToken  
                    }
                });
                const result = await response.json();
                if (result.status === 'success') {
                    window.location.reload();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Error details:', error);
                alert(`Error posting draft: ${error.message}`);
            }
        }
    });
});

document.querySelectorAll('.postThreadXBtn').forEach(button => {
    button.addEventListener('click', async function() {
        const post_id = this.getAttribute('post_id');
        if (confirm('Are you sure you want to post this thread to X?')) {
            try {
                const response = await fetch('/draft/post_thread_x', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.csrfToken
                    },
                    body: JSON.stringify({ post_id: post_id })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    window.location.reload();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Error details:', error);
                alert(`Error posting thread to X: ${error.message}`);
            }
        }
    });
});