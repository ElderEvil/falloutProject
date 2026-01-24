## Room Destruction Error Handling
- Backend validation errors for room destruction were being swallowed by the store action.
- Store actions should throw errors with descriptive messages from the backend (error.response.data.detail) to allow components to handle them.
## Room Destruction Error Handling
- Backend validation errors for room destruction were being swallowed by the store action.
- Store actions should throw errors with descriptive messages from the backend (error.response.data.detail) to allow components to handle them.
