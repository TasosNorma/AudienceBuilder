document.addEventListener('DOMContentLoaded', function() {
    const showPromptsBtn = document.getElementById('showPromptsBtn');
    const promptsDropdown = document.getElementById('promptsDropdown');
    const promptsLoading = document.getElementById('promptsLoading');
    const urlForm = document.getElementById('urlForm');
    const urlInput = document.querySelector('input[name="url"]');
    
    // Show prompts dropdown when button is clicked
    showPromptsBtn.addEventListener('click', async function() {
        const url = urlInput.value.trim();
        
        if (!url) {
            alert('Please enter a URL first');
            return;
        }
        
        // Show dropdown
        promptsDropdown.style.display = 'block';
        
        // Only load prompts if not already loaded
        if (promptsLoading) {
            try {
                const response = await fetch('/user/prompts?type=1');
                const result = await response.json();
                
                // Clear loading spinner
                promptsDropdown.innerHTML = '';
                
                if (result.status === 'success') {
                    if (result.prompts.length === 0) {
                        promptsDropdown.innerHTML = '<div class="dropdown-item">No prompts available</div>';
                    } else {
                        // Add each prompt as a dropdown item
                        result.prompts.forEach(prompt => {
                            const item = document.createElement('a');
                            item.className = 'dropdown-item';
                            item.href = '#';
                            item.textContent = prompt.name;
                            item.dataset.promptId = prompt.id;
                            
                            item.addEventListener('click', handlePromptSelection);
                            
                            promptsDropdown.appendChild(item);
                        });
                    }
                } else {
                    promptsDropdown.innerHTML = `<div class="dropdown-item text-danger">Error: ${result.message}</div>`;
                }
            } catch (error) {
                console.error('Error loading prompts:', error);
                promptsDropdown.innerHTML = '<div class="dropdown-item text-danger">Failed to load prompts</div>';
            }
        }
    });
    
    // Handle prompt selection for drafting
    async function handlePromptSelection(event) {
        event.preventDefault();
        
        const promptId = this.dataset.promptId;
        const url = urlInput.value.trim();
        
        // Show loading spinner
        urlForm.classList.add('loading');
        promptsDropdown.style.display = 'none';
        
        try {
            const response = await fetch('/draft/draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    url: url,
                    prompt_id: promptId
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Redirect or reload the page
                window.location.reload();
            } else {
                alert(result.message);
                urlForm.classList.remove('loading');
            }
        } catch (error) {
            console.error('Error drafting post:', error);
            alert(`Error drafting post: ${error.message}`);
            urlForm.classList.remove('loading');
        }
    }
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#showPromptsBtn') && !e.target.closest('#promptsDropdown')) {
            promptsDropdown.style.display = 'none';
        }
    });
});
    