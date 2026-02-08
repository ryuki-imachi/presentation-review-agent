import { useAuthenticator } from "@aws-amplify/ui-react";

function App() {
  const { user, signOut } = useAuthenticator();

  return (
    <main>
      <h1>Presentation Review Agent</h1>
      <p>ログイン中: {user?.signInDetails?.loginId}</p>
      <button onClick={signOut}>サインアウト</button>
    </main>
  );
}

export default App;
