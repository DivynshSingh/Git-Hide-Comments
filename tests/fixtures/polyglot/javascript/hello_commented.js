// Hello World in JavaScript
// Simple greeting example

/* Configuration */
const greeting = "Hello";
const target = "World"; // who to greet

/**
 * Prints a greeting message.
 * @param {string} name - The name to greet
 */
function greet(name) {
    // Build the message
    const msg = `${greeting}, ${name}!`; // template literal
    console.log(msg); /* log to console */
}

// Execute
greet(target);
