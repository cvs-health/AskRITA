#!/bin/bash

# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Test AskRITA across multiple Python versions using Docker.
# See docs/docker-testing.md for full documentation.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

PYTHON_VERSIONS=("3.11" "3.12" "3.13" "3.14")

echo -e "${BLUE}Testing AskRITA across Python versions using Docker${NC}"
echo -e "${BLUE}===================================================${NC}"

test_python_version() {
    local version=$1
    local container_name="askrita-test-py${version//./}"

    echo -e "\n${YELLOW}Testing Python ${version}${NC}"
    echo -e "${YELLOW}================================${NC}"

    docker rm -f $container_name 2>/dev/null || true

    echo -e "${BLUE}Building Docker image for Python ${version}...${NC}"
    docker build -t askrita-test:py${version//./} \
        --build-arg PYTHON_VERSION=${version} \
        -f Dockerfile.test . || {
        echo -e "${RED}Failed to build Docker image for Python ${version}${NC}"
        return 1
    }

    echo -e "${BLUE}Running tests in Python ${version} container...${NC}"
    docker run --name $container_name \
        -v "$(pwd):/app" \
        -e OPENAI_API_KEY=test-key-for-testing \
        -e PYTHONPATH=/app \
        askrita-test:py${version//./} || {
        echo -e "${RED}Tests failed for Python ${version}${NC}"
        return 1
    }

    echo -e "${GREEN}Python ${version} tests passed${NC}"
    docker rm -f $container_name 2>/dev/null || true
}

test_all_versions() {
    local failed_versions=()
    local success_count=0

    for version in "${PYTHON_VERSIONS[@]}"; do
        if test_python_version "$version"; then
            ((success_count++))
        else
            failed_versions+=("$version")
        fi
    done

    echo -e "\n${BLUE}Results${NC}"
    echo -e "${BLUE}=======${NC}"
    echo -e "${GREEN}Passed: ${success_count}/${#PYTHON_VERSIONS[@]} versions${NC}"

    if [ ${#failed_versions[@]} -eq 0 ]; then
        echo -e "${GREEN}All Python versions passed!${NC}"
        return 0
    else
        echo -e "${RED}Failed: ${failed_versions[*]}${NC}"
        return 1
    fi
}

cleanup() {
    echo -e "${YELLOW}Cleaning up Docker images...${NC}"
    for version in "${PYTHON_VERSIONS[@]}"; do
        docker rmi -f askrita-test:py${version//./} 2>/dev/null || true
    done
    echo -e "${GREEN}Cleanup completed${NC}"
}

case "${1:-all}" in
    "3.11"|"3.12"|"3.13"|"3.14")
        test_python_version "$1"
        ;;
    "all")
        test_all_versions
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|"--help"|"-h")
        echo "Usage: $0 [VERSION|all|cleanup|help]"
        echo ""
        echo "Commands:"
        echo "  3.11, 3.12, 3.13, 3.14  Test a specific Python version"
        echo "  all               Test all Python versions (default)"
        echo "  cleanup           Remove all test Docker images"
        echo "  help              Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                # Test all versions"
        echo "  $0 3.12           # Test only Python 3.12"
        echo "  $0 cleanup        # Clean up Docker images"
        echo ""
        echo "See docs/docker-testing.md for full documentation."
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
