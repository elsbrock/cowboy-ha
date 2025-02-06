{
  description = "Cowboy Home Assistant Integration Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          pip
          virtualenv
        ]);
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            git
            pre-commit
          ];

          shellHook = ''
            # Create virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              python -m venv .venv
            fi

            # Activate virtual environment
            source .venv/bin/activate

            # Install dependencies if needed
            if [ ! -f .venv/.installed ]; then
              echo "Installing dependencies..."
              pip install --upgrade pip
              pip install -r requirements.txt
              touch .venv/.installed
            fi

            # Add .venv/bin to PATH
            export PATH="$PWD/.venv/bin:$PATH"

            echo "Development environment ready!"
            echo ""
            echo "Quick start:"
            echo "1. Run 'hass -c config' to start Home Assistant"
            echo "2. Visit http://localhost:8123 in your browser"
            echo "3. Run 'pytest tests/' to run tests"
          '';
        };
      }
    );
}
