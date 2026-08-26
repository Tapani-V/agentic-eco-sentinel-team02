import React, { createContext, useCallback, useContext, useState } from 'react';

interface AnnouncerContextValue {
  announce: (message: string) => void;
}

const AnnouncerContext = createContext<AnnouncerContextValue>({ announce: () => {} });

/** Hook to push announcements into the live region. */
export function useAnnouncer(): AnnouncerContextValue {
  return useContext(AnnouncerContext);
}

export interface AnnouncerProviderProps {
  children: React.ReactNode;
}

/** Provider that renders a visually-hidden aria-live="polite" region for screen reader announcements. */
export function AnnouncerProvider({ children }: AnnouncerProviderProps): React.JSX.Element {
  const [messages, setMessages] = useState<string[]>([]);

  const announce = useCallback((message: string) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  return (
    <AnnouncerContext.Provider value={{ announce }}>
      {children}
      <div aria-live="polite" aria-atomic="false" className="sr-only" role="log">
        {messages.map((msg, i) => (
          <p key={i}>{msg}</p>
        ))}
      </div>
    </AnnouncerContext.Provider>
  );
}
