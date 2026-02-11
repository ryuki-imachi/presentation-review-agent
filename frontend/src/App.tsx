import { useAuthenticator } from "@aws-amplify/ui-react";
import { useAudioUpload } from "./hooks/useAudioUpload";
import { AudioUploader } from "./components/upload";
import { AnalysisRunner } from "./components/analysis";
import { Header } from "./components/layout";

function App() {
  const { user, signOut } = useAuthenticator();
  const audioUpload = useAudioUpload();

  return (
    <div className="app">
      <Header userEmail={user?.signInDetails?.loginId} signOut={signOut} />
      <main className="app__main">
        <AudioUploader {...audioUpload} />
        <AnalysisRunner s3Key={audioUpload.uploadedPath} onDataDeleted={audioUpload.reset} />
      </main>
    </div>
  );
}

export default App;
