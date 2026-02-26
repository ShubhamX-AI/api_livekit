# Tool Design Guidelines

### Writing Good Tool Descriptions

The `tool_description` is crucial - it's what the LLM uses to decide when to call your tool:

!!! success "Good Examples"

    ```json
    {
      "tool_description": "Get the current stock price for a given ticker symbol. Use this when the user asks about stock prices, investments, or financial data."
    }
    ```

    ```json
    {
      "tool_description": "Schedule an appointment for the user. Only use this when the user explicitly asks to book, schedule, or make an appointment."
    }
    ```

!!! failure "Bad Examples"

    ```json
    {
      "tool_description": "Weather tool"
    }
    ```

    ```json
    {
      "tool_description": "This function gets weather data from our API and returns it in JSON format"
    }
    ```

### Parameter Design

- **Be specific** with parameter descriptions
- **Use enums** when there are limited valid values
- **Set required appropriately** - only mark truly required fields as required
- **Choose the right type** - use `number` for numeric values, not strings

### Execution Type Selection

| Use Webhook When                | Use Static Return When      |
| ------------------------------- | --------------------------- |
| Data changes frequently         | Information never changes   |
| External API integration needed | No external dependencies    |
| User-specific data required     | Same response for all users |
| Complex business logic          | Simple constant values      |
