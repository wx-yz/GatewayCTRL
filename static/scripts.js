// Add smooth scrolling
document.addEventListener('DOMContentLoaded', function() {
    // Create progress bar
    const progressContainer = document.createElement('div');
    progressContainer.className = 'progress-container';
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressContainer.appendChild(progressBar);
    document.body.insertBefore(progressContainer, document.body.firstChild);

    // Initialize loading state
    let loadingSteps = [
        { name: 'Initializing...', progress: 10 },
        { name: 'Loading gateways...', progress: 30 },
        { name: 'Fetching API data...', progress: 60 },
        { name: 'Rendering UI...', progress: 90 },
        { name: 'Complete', progress: 100 }
    ];

    // Update progress bar
    function updateProgress(step) {
        progressBar.style.width = `${step.progress}%`;
        // Update loading message in Streamlit
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: step.name
        }, '*');
    }

    // Simulate loading steps
    let currentStep = 0;
    const interval = setInterval(() => {
        if (currentStep < loadingSteps.length) {
            updateProgress(loadingSteps[currentStep]);
            currentStep++;
        } else {
            clearInterval(interval);
            // Hide progress bar when complete
            progressContainer.style.opacity = '0';
            setTimeout(() => {
                progressContainer.style.display = 'none';
            }, 500);
        }
    }, 500);

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Add loading state to buttons
    document.querySelectorAll('.stButton').forEach(button => {
        button.addEventListener('click', function() {
            this.classList.add('loading');
            setTimeout(() => {
                this.classList.remove('loading');
            }, 1000);
        });
    });

    // Add tooltips
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = element.getAttribute('data-tooltip');
        document.body.appendChild(tooltip);
        
        element.addEventListener('mouseenter', (e) => {
            const rect = element.getBoundingClientRect();
            tooltip.style.left = `${rect.left + (rect.width / 2)}px`;
            tooltip.style.top = `${rect.top - 30}px`;
            tooltip.style.display = 'block';
        });

        element.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });
    });

    // Add copy to clipboard functionality
    document.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy');
            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalText = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => {
                    this.textContent = originalText;
                }, 2000);
            });
        });
    });

    // Add search functionality to tables
    document.querySelectorAll('.searchable-table').forEach(table => {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search...';
        searchInput.className = 'table-search';
        table.parentNode.insertBefore(searchInput, table);

        searchInput.addEventListener('input', function() {
            const searchText = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchText) ? '' : 'none';
            });
        });
    });

    // Add responsive table handling
    document.querySelectorAll('.stTable').forEach(table => {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}); 