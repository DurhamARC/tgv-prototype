// Typesense Search Client Prototype Script
// This script is responsible for initializing the Typesense client,
// handling user input, performing searches, and displaying results.

// Global variables
let client;
let currentPage = 1;

// Popup div consts (hidden by default)
const popup = document.createElement('div');
const closeButton = document.createElement('button');
const popupContent = document.createElement('div');


/**
 * Load the Typesense client configuration from a separate JavaScript file.
 * This file should export a global variable named TYPESENSE_CLIENT_CONFIG.
 */
async function loadConfig() {
    try {
        const response = await fetch('/config.js');
        const scriptText = await response.text();
        const config = eval(scriptText + '; TYPESENSE_CLIENT_CONFIG;');
        console.log('Typesense client config loaded:', config);
        return new Typesense.Client(config);
    } catch (error) {
        console.error('Failed to load Typesense client config:', error);
        throw error;
    }
}


/**
 * Debounce function to limit the rate at which a function can be called.
 * @param {function} func - The function to debounce.
 * @param {number} wait - The number of milliseconds to wait before calling the function.
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}


/**
 * Perform a search using the Typesense client.
 * The search is triggered by user input in the search box.
 * It retrieves the search query, source filter, and results per page 
 * from the UI, and calls the Typesense client to perform the search.
 * 
 * The search function should be debounced on-call to limit the number 
 * of requests sent to the server.
 */
async function search() {
    const query = document.getElementById('search-box').value;
    const sourceFilter = document.getElementById('source-filter').value;
    const perPage = parseInt(document.getElementById('results-per-page').value) || 10;

    if (query.length === 0) {
        document.getElementById('results').innerHTML = '';
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    const searchParameters = {
        q: query,
        query_by: 'ocr_text_original',
        per_page: perPage,
        page: currentPage,
        highlight_full_fields: 'ocr_text_original',
        sort_by: '_text_match:desc'
    };

    if (sourceFilter) {
        searchParameters.filter_by = `source:${sourceFilter}`;
    }

    try {
        const searchResults = await client.collections('documents').documents().search(searchParameters);
        displayResults(searchResults);
        displayPagination(searchResults.found, perPage);
    } catch (error) {
        console.error('Search error:', error);
    }
}


/**
 * Create a popup for displaying full text results.
 * The popup is displayed when the user clicks the "View Full Text" button.
 */
function createPopup() {
    popup.id = 'text-popup';

    closeButton.textContent = 'X';
    closeButton.className = 'close-button';
    closeButton.onclick = () => {
        popup.style.display = 'none';
        document.body.style.overflow = 'auto'; // Re-enable scrolling
    };

    popupContent.id = 'popup-content';

    popup.appendChild(closeButton);
    popup.appendChild(popupContent);
    document.body.appendChild(popup);
}

popup.addEventListener('click', (event) => {
  if (!popupContent.contains(event.target) && event.target !== closeButton) {
    popup.style.display = 'none';
    document.body.style.overflow = 'auto';
  }
});

/**
 * Display the search results in the UI.
 * It creates a card for each result, showing the title, snippet, and action buttons.
 * The results are displayed in a container with pagination.
 * @param {object} results - The search results from Typesense.
 * @returns 
 */
function displayResults(results) {
    const resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';

    if (results.hits.length === 0) {
        resultsContainer.innerHTML = '<div class="notification is-info">No results found</div>';
        return;
    }

    const query = document.getElementById('search-box').value.trim();

    results.hits.forEach(result => {
        const card = document.createElement('div');
        card.className = 'card';

        const cardContent = document.createElement('div');
        cardContent.className = 'card-content';

        const titleContainer = document.createElement('div');
        titleContainer.className = 'is-flex is-justify-content-space-between is-align-items-center';

        const title = document.createElement('p');
        title.className = 'title is-4';
        title.textContent = `${result.document.title_full} - Date ${result.document.date} - Page ${result.document.page_number}`;

        const sourceTag = document.createElement('a');
        sourceTag.className = 'tag is-info source-tag';
        sourceTag.href = result.document.remote_path;
        sourceTag.target = '_blank';
        sourceTag.textContent = result.document.source;


        titleContainer.appendChild(title);
        titleContainer.appendChild(sourceTag);

        const snippet = document.createElement('div');
        snippet.className = 'content';

        if (result.highlights.length > 0) {
            const normalizedQuery = query.normalize('NFC').toLowerCase();

            // Attempt to find a relevant highlight
            const relevantHighlight = result.highlights.find(h =>
                h.snippet.normalize('NFC').toLowerCase().includes(normalizedQuery)
            );

            if (relevantHighlight && relevantHighlight.snippet) {
                // Convert snippet to plain text before highlighting
                const plainTextSnippet = relevantHighlight.snippet.replace(/<[^>]*>/g, '');

                // Escape regex special characters in the query
                const escapedQuery = normalizedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`(${escapedQuery})`, 'gi');

                // Apply highlighting
                const highlightedSnippet = plainTextSnippet.replace(regex, '<mark>$1</mark>');

                snippet.innerHTML = highlightedSnippet;
            } else {
                // Fallback to a plain text excerpt if no valid highlight is found
                snippet.textContent = result.document.ocr_text_original.substring(0, 200) + '...';
            }
        } else {
            snippet.textContent = result.document.ocr_text_original.substring(0, 200) + '...'; // Fallback if no highlight
        }


        const actions = document.createElement('div');
        actions.className = 'field is-grouped mt-4';

        const viewFullTextButton = document.createElement('p');
        viewFullTextButton.className = 'control';
        viewFullTextButton.innerHTML = `<button class="button is-link">View Full Text</button>`;

        viewFullTextButton.onclick = () => {
            if (result.document.ocr_text_original) {
                const query = document.getElementById('search-box').value.trim();

                if (query) {
                    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // Escape regex special characters
                    const regex = new RegExp(`(${escapedQuery})`, 'gi'); // Case-insensitive match
                    const highlightedText = result.document.ocr_text_original.replace(regex, '<mark>$1</mark>'); // Highlight occurrences
                    popupContent.innerHTML = `<pre>${highlightedText}</pre>`;
                } else {
                    popupContent.innerHTML = `<pre>${result.document.ocr_text_original}</pre>`;
                }

                popup.style.display = 'block';
                document.body.style.overflow = 'hidden'; // Disable scrolling when popup is open
            } else {
                popupContent.innerHTML = '<p class="notification is-warning">No text available.</p>';
                popup.style.display = 'block';
            }
        };


        const imageButton = document.createElement('p');
        imageButton.className = 'control';
        imageButton.innerHTML = `<a href="${result.document.image_url}" target="_blank" class="button is-link is-light">View Image</a>`;

        actions.appendChild(viewFullTextButton);
        actions.appendChild(imageButton);

        cardContent.appendChild(titleContainer);
        cardContent.appendChild(snippet);
        cardContent.appendChild(actions);
        card.appendChild(cardContent);
        resultsContainer.appendChild(card);
    });
}


/**
 * Function which displays pagination controls based on the total number of results and results per page.
 * It creates "Previous" and "Next" buttons to navigate through the pages.
 * The buttons are disabled when the user is on the first or last page.
 * @param {int} total 
 * @param {int} perPage 
 * @returns 
 */
function displayPagination(total, perPage) {
    const totalPages = Math.ceil(total / perPage);
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    const nav = document.createElement('nav');
    nav.className = 'pagination';

    const previousButton = document.createElement('a');
    previousButton.className = `pagination-previous ${currentPage === 1 ? 'is-disabled' : ''}`;
    previousButton.textContent = 'Previous';
    previousButton.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            search();
        }
    };

    const nextButton = document.createElement('a');
    nextButton.className = `pagination-next ${currentPage === totalPages ? 'is-disabled' : ''}`;
    nextButton.textContent = 'Next';
    nextButton.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            search();
        }
    };

    nav.appendChild(previousButton);
    nav.appendChild(nextButton);
    pagination.appendChild(nav);
}


/**
 * "Main" function
 * Runs when the DOM is fully loaded.
 * It initializes the Typesense client, sets up event listeners for the search box,
 * source filter, and results per page dropdowns.
 * It also creates the popup for displaying full text results.
 */
document.addEventListener("DOMContentLoaded", function(event) { 
    
    loadConfig().then(tsClient => {
        client = tsClient;
        console.log('Typesense client initialized');
    });

    document.getElementById('search-box').addEventListener('input', debounce(search, 300));
    document.getElementById('source-filter').addEventListener('change', search);
    document.getElementById('results-per-page').addEventListener('change', search);
    console.log('Event listeners registered');

    createPopup();
    console.log('Popup created');
});
