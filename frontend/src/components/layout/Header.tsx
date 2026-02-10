import "./Header.css";

interface Props {
  userEmail: string | undefined;
  signOut: () => void;
}

export function Header({ userEmail, signOut }: Props) {
  return (
    <header className="header">
      <div className="header__inner">
        <h1 className="header__title">Presentation Review Agent</h1>
        <div className="header__user">
          <span className="header__email">{userEmail ?? "ログイン中"}</span>
          <button className="btn btn--ghost btn--sm" onClick={signOut}>
            サインアウト
          </button>
        </div>
      </div>
    </header>
  );
}
