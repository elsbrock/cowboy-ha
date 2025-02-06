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
          pytest
          pytest-cov
          pytest-asyncio
          black
          pylint
          hatchling
          colorlog
        ]);
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv

            # Tools used in CI/development
            yq-go    # For JSON/YAML processing
            zip     # For packaging releases
            git     # For version control

            # Development tools
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
              pip install home-assistant
              pip install pytest-homeassistant-custom-component || exit 1
              pip install -e ".[dev]" || exit 1
              touch .venv/.installed
            fi

            # Add .venv/bin to PATH
            export PATH="$PWD/.venv/bin:$PATH"

            # Create config directory if it doesn't exist
            if [ ! -d config ]; then
              mkdir -p config
            fi

            # Create basic configuration.yaml if it doesn't exist
            if [ ! -f config/configuration.yaml ]; then
              echo "default_config:" > config/configuration.yaml
              echo "# Uncomment below to enable debug logging for your component" >> config/configuration.yaml
              echo "# logger:" >> config/configuration.yaml
              echo "#   default: info" >> config/configuration.yaml
              echo "#   logs:" >> config/configuration.yaml
              echo "#     custom_components.cowboy: debug" >> config/configuration.yaml
            fi

            echo "Development environment ready!"
            echo ""
            echo "Quick start:"
            echo "1. Run 'hass -c config' to start Home Assistant"
            echo "2. Visit http://localhost:8123 in your browser"
            echo "3. Run 'pytest tests/' to run tests"
            echo ""
            echo "Development tips:"
            echo "- Edit config/configuration.yaml to configure the integration"
            echo "- Home Assistant will automatically reload when you make changes"
            echo "- Use 'hass --debug -c config' for debug output"
          '';
        };
      }
    );
}
