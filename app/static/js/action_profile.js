// Add event listener for dropdown toggle
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

// Add event listeners for LinkedIn and X posting
document.querySelectorAll('.post-linkedin').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to post this draft to LinkedIn?')) {
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
                alert(`Error posting to LinkedIn: ${error.message}`);
            }
        }
    });
});

document.querySelectorAll('.post-x').forEach(button => {
    button.addEventListener('click', async function() {
        const comparison_id = this.getAttribute('comparison_id');
        if (confirm('Are you sure you want to post this draft to X?')) {
            try {
                // First get the post ID associated with this comparison
                const postResponse = await fetch(`/comparison/${comparison_id}/get_post`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                const postResult = await postResponse.json();
                
                if (postResult.status !== 'success') {
                    throw new Error(postResult.message || 'Failed to get post data');
                }
                
                // Now post the thread to X
                const response = await fetch('/draft/post_thread_x', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.csrfToken  
                    },
                    body: JSON.stringify({
                        post_id: postResult.post.id
                    })
                });
                
                const result = await response.json();
                if (result.status === 'success') {
                    window.location.reload();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Error details:', error);
                alert(`Error posting to X: ${error.message}`);
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