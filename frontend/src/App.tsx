import { useAuthenticator } from "@aws-amplify/ui-react";
import { useAudioUpload } from "./hooks/useAudioUpload";
import { AudioUploader } from "./components/upload";
import { AnalysisRunner } from "./components/analysis";

function App() {
  const { user, signOut } = useAuthenticator();
  const audioUpload = useAudioUpload();

  return (
    <main>
      <h1>Presentation Review Agent</h1>
      <p>ログイン中: {user?.signInDetails?.loginId}</p>
      <button onClick={signOut}>サインアウト</button>
      <AudioUploader {...audioUpload} />
      <AnalysisRunner s3Key={audioUpload.uploadedPath} />
    </main>
  );
}

export default App;
