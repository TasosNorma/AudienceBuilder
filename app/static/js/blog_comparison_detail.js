// Add event listener for draft post
document.querySelectorAll('.draft-post').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to draft a post?')) {
            try {
                const response = await fetch(`/comparison/${comparison_id}/draft`, {
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
                alert(`Error drafting post: ${error.message}`);
            }
        }
    });
});

// Add event listener for ingore comparison
document.querySelectorAll('.ignore-comparison').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to ignore?')) {
            try {
                const response = await fetch(`/comparison/${comparison_id}/ignore`, {
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
                alert(`Error ignoring comparison: ${error.message}`);
            }
        }
    });
});

// Add event listener for post draft
document.querySelectorAll('.post-comparison').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to ignore the draft?')) {
            try {
                const response = await fetch(`/comparison/${comparison_id}/post`, {
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
                alert(`Error drafting post: ${error.message}`);
            }
        }
    });
});

// Add event listener for ingore-draft
document.querySelectorAll('.ignore-draft').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to ignore the draft?')) {
            try {
                const response = await fetch(`/comparison/${comparison_id}/ignore_draft`, {
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
                alert(`Error ignoring draft: ${error.message}`);
            }
        }
    });
});