// Add event listener for draft post
document.querySelectorAll('.dropdown-toggle').forEach(button => {
    button.addEventListener('click', async function() {
        const comparisonId = this.id.replace('draftDropdown', '');
        const dropdownMenu = document.querySelector(`.prompt-dropdown[data-comparison-id="${comparisonId}"]`);
        
        // Only load prompts if not already loaded
        if (dropdownMenu.querySelector('.spinner-border')) {
            try {
                const response = await fetch('/user/prompts');
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

// Handle group selection for adding comparison to group
async function handleGroupSelection(event) {
    event.preventDefault();
    
    const groupId = this.dataset.groupId;
    const comparisonId = this.dataset.comparisonId;
    
    if (confirm('Are you sure you want to add this article to the selected group?')) {
        try {
            const response = await fetch('/groups/add_action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken
                },
                body: JSON.stringify({
                    comparison_id: comparisonId,
                    group_id: groupId
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                alert('Article added to group successfully');
                window.location.reload();
            } else {
                alert(result.message || 'Failed to add article to group');
            }
        } catch (error) {
            console.error('Error adding article to group:', error);
            alert(`Error adding article to group: ${error.message}`);
        }
    }
}

// Add event listener for group button clicks
document.querySelectorAll('[id^="groupDropdown"]').forEach(button => {
    button.addEventListener('click', async function() {
        const comparisonId = this.id.replace('groupDropdown', '');
        const dropdownMenu = document.querySelector(`.group-dropdown[data-comparison-id="${comparisonId}"]`);
        
        // Only load groups if not already loaded
        if (dropdownMenu.querySelector('.spinner-border')) {
            try {
                const response = await fetch('/user/groups');
                const result = await response.json();
                
                if (result.status === 'success') {
                    // Clear loading spinner
                    dropdownMenu.innerHTML = '';
                    
                    if (!result.groups || result.groups.length === 0) {
                        dropdownMenu.innerHTML = '<li><div class="dropdown-item">No groups available</div></li>';
                    } else {
                        // Add each group as a dropdown item
                        result.groups.forEach(group => {
                            const item = document.createElement('li');
                            const link = document.createElement('a');
                            link.className = 'dropdown-item';
                            link.href = '#';
                            link.textContent = group.name;
                            link.dataset.groupId = group.id;
                            link.dataset.comparisonId = comparisonId;
                            
                            link.addEventListener('click', handleGroupSelection);
                            
                            item.appendChild(link);
                            dropdownMenu.appendChild(item);
                        });
                    }
                } else {
                    dropdownMenu.innerHTML = `<li><div class="dropdown-item text-danger">Error: ${result.message || 'Failed to load groups'}</div></li>`;
                }
            } catch (error) {
                console.error('Error loading groups:', error);
                dropdownMenu.innerHTML = '<li><div class="dropdown-item text-danger">Failed to load groups</div></li>';
            }
        }
    });
});

// add event listener to ignore and learn
document.querySelectorAll('.ignore-and-learn').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('This will change your profile description, are you sure you want to do this?')) {
            try {
                const response = await fetch(`/comparison/ignore_and_learn`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.csrfToken
                    },
                    body: JSON.stringify({
                        comparison_id: comparison_id
                    })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    window.location.reload();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Error ignoring and learning:', error);
                alert(`Error ignoring and learning: ${error.message}`);
            }
        }
    });
});