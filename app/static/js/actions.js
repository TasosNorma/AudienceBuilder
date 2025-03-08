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

// Add event listener for ignore comparison
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
        if (confirm('Are you sure you want to post this draft?')) {
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
                alert(`Error posting draft: ${error.message}`);
            }
        }
    });
});

// Add event listener for ignore-draft
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

// Add event listener for redraft comparison
document.querySelectorAll('.redraft-comparison').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to re-draft this post?')) {
            try {
                const response = await fetch(`/comparison/${comparison_id}/redraft`, {
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


// Hover card functionality
document.addEventListener('DOMContentLoaded', function() {
    const hoverCard = document.getElementById('action-hover-card');
    const hoverCardTitle = document.getElementById('hover-card-title');
    const hoverCardSummary = document.getElementById('hover-card-summary');
    const hoverCardDraftSection = document.getElementById('hover-card-draft-section');
    const hoverCardDraftText = document.getElementById('hover-card-draft-text');

    // Add event listeners to all action rows
    document.querySelectorAll('.action-row').forEach(row => {
        row.addEventListener('mouseenter', async function(e) {
            // Get data from the row's data attributes
            const title = this.getAttribute('data-title');
            const summary = this.getAttribute('data-summary');
            const hasPost = this.getAttribute('data-has-post') === 'True';
            const comparisonId = this.getAttribute('data-comparison-id');

            // Set the basic information
            hoverCardTitle.textContent = title;
            hoverCardSummary.textContent = summary || 'No summary available';

            if (hasPost) {
                try {
                    const response = await fetch(`/comparison/${comparisonId}/get_post`);
                    const data = await response.json();
                    
                    if (data.status === 'success' && data.post) {
                        hoverCardDraftText.textContent = data.post.plain_text || 'Draft content not available';
                        hoverCardDraftSection.classList.remove('d-none');
                    } else {
                        hoverCardDraftSection.classList.add('d-none');
                    }
                } catch (error) {
                    console.error('Error fetching post data:', error);
                    hoverCardDraftSection.classList.add('d-none');
                }
            } else {
                hoverCardDraftSection.classList.add('d-none');
            }
            // Position the hover card
            const rect = this.getBoundingClientRect();
            const tableRect = document.querySelector('.table-responsive').getBoundingClientRect();
            
            // hoverCard.style.top = `${rect.top + window.scrollY - 20}px`;
            // hoverCard.style.left = `${tableRect.left - hoverCard.offsetWidth - 20}px`;
            
            // Show the hover card
            hoverCard.classList.remove('d-none');
        });
        // row.addEventListener('mouseleave', function() {
        //     // Hide the hover card when mouse leaves the row
        //     hoverCard.classList.add('d-none');
        // });
    });
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.action-row') && !e.target.closest('.action-hover-card')) {
            hoverCard.classList.add('d-none');
        }
    });
});