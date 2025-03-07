document.querySelectorAll('.redraftBtn').forEach(button => {
    button.addEventListener('click', async function() {
        const post_id = this.getAttribute('post_id');
        if (confirm('Are you sure you want to re-draft a draft?')) {
            try {
                const response = await fetch(`/draft/${post_id}/redraft`, {
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
                alert(`Error re-drafting post: ${error.message}`);
            }
        }
    });
});

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