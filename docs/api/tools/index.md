# Tool Management

This section covers creating, updating, and managing tools for your assistants.

## Overview

Tools are custom functions that extend your assistant's capabilities. When the LLM determines a tool should be called, the system executes it and returns the result to continue the conversation.

### Execution Types

| Type              | Description                       | Use Case                                                     |
| :---------------- | :-------------------------------- | :----------------------------------------------------------- |
| **Webhook**       | HTTP POST request to external URL | Fetch live data (weather, stock prices, user info)           |
| **Static Return** | Return a fixed value              | Provide constant information (support email, business hours) |

Explore the sub-sections to interact with the Tools API:

- [Create Tool](create.md)
- [List Tools](list.md)
- [Get Tool Details](get.md)
- [Update Tool](update.md)
- [Delete Tool](delete.md)
- [Attach Tools](attach.md)
- [Detach Tools](detach.md)
- [Webhook Payload format](webhook.md)
- [Design Guidelines](design.md)
