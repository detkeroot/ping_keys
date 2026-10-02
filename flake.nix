{
  description = "Gemini Nexus DB (ping_keys) - Gemini & Gemma API key validator and stream balancer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          pyqt6
          pyqtdarktheme
          pysocks
          pytest
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          name = "ping_keys_dev_shell";
          packages = [
            pythonEnv
            pkgs.qt6.qtwayland
            pkgs.sqlite
            pkgs.ruff
          ];

          shellHook = ''
            export PYTHONUNBUFFERED=1
            export QT_QPA_PLATFORM="wayland;xcb"
            echo "🚀 [Gemini Nexus DB] Dev environment loaded (Python $(python3 --version), PyQt6 Native Wayland)"
          '';
        };

        packages.default = pkgs.writeShellApplication {
          name = "ping-keys";
          runtimeInputs = [
            pythonEnv
            pkgs.qt6.qtwayland
          ];
          text = ''
            export QT_QPA_PLATFORM="wayland;xcb"
            if [ -d "$PWD/gemini_nexus" ]; then
              export PYTHONPATH="$PWD''${PYTHONPATH:+:$PYTHONPATH}"
            else
              export PYTHONPATH="${./.}''${PYTHONPATH:+:$PYTHONPATH}"
            fi
            exec python3 -m gemini_nexus.main "$@"
          '';
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ping-keys";
        };
      }
    );
}
