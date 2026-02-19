import { configureStore } from "@reduxjs/toolkit";

import { agentApi } from "../features/agent/api/agentApi";
import agentReducer from "../features/agent/model/agentSlice";
import { chatApi } from "../features/chat/api/chatApi";
import chatReducer from "../features/chat/model/chatSlice";

export const store = configureStore({
  reducer: {
    agent: agentReducer,
    chat: chatReducer,
    [agentApi.reducerPath]: agentApi.reducer,
    [chatApi.reducerPath]: chatApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(chatApi.middleware, agentApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
