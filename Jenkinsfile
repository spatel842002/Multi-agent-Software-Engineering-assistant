// Reference Jenkins pipeline mirroring .github/workflows/ci.yml, for teams
// that run Jenkins instead of (or alongside) GitHub Actions. Requires a
// Jenkins agent with Docker, Python 3.11, and Node.js 22 available (or use
// the Docker Pipeline plugin with the images referenced below).
// See docs/deployment.md for the Jenkins-specific setup notes.
pipeline {
    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Secret scan') {
            steps {
                sh 'docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source=/repo --no-git -v'
            }
        }

        stage('Backend') {
            agent {
                docker { image 'python:3.11-slim' }
            }
            stages {
                stage('Install') {
                    steps {
                        dir('backend') {
                            sh 'pip install -r requirements-dev.txt'
                        }
                    }
                }
                stage('Lint & types') {
                    steps {
                        dir('backend') {
                            sh 'ruff format --check app tests'
                            sh 'ruff check app tests'
                            sh 'mypy app'
                        }
                    }
                }
                stage('Test') {
                    steps {
                        dir('backend') {
                            sh 'pytest -m "not integration and not model_download" --cov --cov-report=xml -q'
                        }
                    }
                    post {
                        always {
                            dir('backend') {
                                junit allowEmptyResults: true, testResults: 'junit.xml'
                            }
                        }
                    }
                }
            }
        }

        stage('Frontend') {
            agent {
                docker { image 'node:22-slim' }
            }
            stages {
                stage('Install') {
                    steps {
                        dir('frontend') {
                            sh 'npm ci'
                        }
                    }
                }
                stage('Lint, test, build') {
                    steps {
                        dir('frontend') {
                            sh 'npx eslint .'
                            sh 'npx prettier --check .'
                            sh 'npx vitest run'
                            sh 'npx tsc -b'
                            sh 'npm run build'
                        }
                    }
                }
            }
        }

        stage('Docker builds') {
            steps {
                sh 'docker build -t masea-backend:${BUILD_NUMBER} ./backend'
                sh 'docker build -t masea-frontend:${BUILD_NUMBER} ./frontend'
            }
        }

        stage('docker compose config') {
            steps {
                sh 'docker compose -f docker-compose.yml config -q'
            }
        }

        stage('Terraform fmt/validate') {
            agent {
                docker { image 'hashicorp/terraform:1.16' }
            }
            steps {
                dir('terraform/eks') {
                    sh 'terraform fmt -check -recursive'
                    sh 'terraform init -backend=false'
                    sh 'terraform validate'
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
