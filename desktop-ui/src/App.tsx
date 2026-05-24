import { useCallback, useState } from 'react';
import PlaygroundConnect from './components/PlaygroundConnect';
import Playground from './components/playground/Playground';
import type { ConnectionConfig } from './lib/types';

function App() {
  const [connectionConfig, setConnectionConfig] = useState<ConnectionConfig | null>(null);

  const handleConnect = useCallback(async (config: ConnectionConfig) => {
    setConnectionConfig(config);
  }, []);

  const handleDisconnect = useCallback(() => {
    setConnectionConfig(null);
  }, []);

  return (
    <div className="h-screen w-screen bg-zinc-950 grid-pattern overflow-hidden">
      {!connectionConfig && (
        <PlaygroundConnect onConnect={handleConnect} />
      )}
      {connectionConfig && (
        <Playground
          config={connectionConfig}
          onConnected={() => {}}
          onDisconnect={handleDisconnect}
        />
      )}
    </div>
  );
}

export default App;
