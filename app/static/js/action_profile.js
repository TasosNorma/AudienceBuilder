// Add event listener for dropdown toggle
document.querySelectorAll('.dropdown-toggle').forEach(button => {
    button.addEventListener('click', async function() {
        const comparisonId = this.id.replace('draftDropdown', '');
        const dropdownMenu = document.querySelector(`.prompt-dropdown[data-comparison-id="${comparisonId}"]`);
        
        // Only load prompts if not already loaded
        if (dropdownMenu.querySelector('.spinner-border')) {
            try {
                const response = await fetch('/user/prompts?type=1');
                const result = await response.json();
                
                if (result.status === 'success') {
                    // Clear loading spinner
                    dropdownMenu.innerHTML = '';
                    
                    if (result.prompts.length === 0) {
                        dropdownMenu.innerHTML = '<li><div class="dropdown-item">No prompts available</div></li>';
                    } else {
                        // Add each prompt as a dropdown item
                        result.prompts.forEach(prompt => {
                            const item = document.createElement('li');
                            const link = document.createElement('a');
                            link.className = 'dropdown-item';
                            link.href = '#';
                            link.textContent = prompt.name;
                            link.dataset.promptId = prompt.id;
                            link.dataset.comparisonId = comparisonId;
                            
                            link.addEventListener('click', handlePromptSelection);
                            
                            item.appendChild(link);
                            dropdownMenu.appendChild(item);
                        });
                    }
                } else {
                    dropdownMenu.innerHTML = `<li><div class="dropdown-item text-danger">Error: ${result.message}</div></li>`;
                }
            } catch (error) {
                console.error('Error loading prompts:', error);
                dropdownMenu.innerHTML = '<li><div class="dropdown-item text-danger">Failed to load prompts</div></li>';
            }
        }
    });
});

// Handle prompt selection for drafting
async function handlePromptSelection(event) {
    event.preventDefault();
    
    const promptId = this.dataset.promptId;
    const comparisonId = this.dataset.comparisonId;
    
    if (confirm('Are you sure you want to draft a post using this prompt?')) {
        try {
            const response = await fetch('/comparison/draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken
                },
                body: JSON.stringify({
                    comparison_id: comparisonId,
                    prompt_id: promptId
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                window.location.reload();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error('Error drafting post:', error);
            alert(`Error drafting post: ${error.message}`);
        }
    }
}

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