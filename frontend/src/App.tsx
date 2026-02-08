import { useAuthenticator } from "@aws-amplify/ui-react";
import { AudioUploader } from "./components/upload";

function App() {
  const { user, signOut } = useAuthenticator();

  return (
    <main>
      <h1>Presentation Review Agent</h1>
      <p>ログイン中: {user?.signInDetails?.loginId}</p>
      <button onClick={signOut}>サインアウト</button>
      <AudioUploader />
    </main>
  );
}

export default App;
