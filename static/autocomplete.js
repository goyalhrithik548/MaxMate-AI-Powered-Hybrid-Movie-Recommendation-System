new autoComplete({
    data: {
      src: films,
    },
    selector: "#autoComplete",
    threshold: 2,
    debounce: 100,
    searchEngine: "strict",
    resultsList: {
        render: true,
        // IMPORTANT: keep the list inside the container so it aligns perfectly
        destination: document.querySelector(".search-box-container"),
        position: "beforeend",
        element: "ul"
    },
    maxResults: 5,
    highlight: true,
    resultItem: {
        content: (data, source) => {
            source.innerHTML = data.match;
        },
        element: "li"
    },
    noResults: () => {
        const result = document.createElement("li");
        result.setAttribute("class", "no_result");
        result.setAttribute("tabindex", "1");
        result.innerHTML = "No Results";
        // Safe check before appending
        const list = document.querySelector(".search-box-container ul");
        if(list) list.appendChild(result);
    },
    onSelection: feedback => {
        const selection = feedback.selection.value;
        const input = document.getElementById('autoComplete');

        // 1. Update the input value
        input.value = selection;

        // 2. Clear the dropdown list & remove focus
        input.blur();
        const list = document.querySelector(".search-box-container ul");
        if(list) list.innerHTML = "";

        // 3. FORCE ENABLE & CLICK THE SEARCH BUTTON
        const btn = document.getElementById("search-btn");

        // Remove the "disabled" lock so clicks actually work
        btn.disabled = false;
        btn.removeAttribute("disabled");

        // Trigger the click event
        btn.click();
    }
});