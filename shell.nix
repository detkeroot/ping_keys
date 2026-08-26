{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    customtkinter
    pysocks
    tkinter
  ]);
in
pkgs.mkShell {
  name = "ping_keys_shell";
  packages = [
    pythonEnv
    pkgs.sqlite
    pkgs.ruff
  ];

  shellHook = ''
    export PYTHONUNBUFFERED=1
    echo "🚀 [Gemini Nexus DB] Shell loaded. Run ./run.sh or python3 ping_keys_NeuroStarNet_v13.9.py"
  '';
}
