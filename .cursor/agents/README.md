# 🤖 Cursor Agents for LaTeX → HTML5 Converter

This directory contains specialized Cursor agent configurations for different aspects of the LaTeX → HTML5 Converter project.

## 🎯 Available Agents

### 🚀 [API Development Agent](api-agent.md)
**Focus**: FastAPI development, API design, web services
- FastAPI application setup and configuration
- API endpoint design and implementation
- Request/response models with Pydantic
- Error handling and validation
- OpenAPI/Swagger documentation

### 🔄 [Conversion Pipeline Agent](conversion-agent.md)
**Focus**: LaTeX processing, Tectonic, LaTeXML integration
- Tectonic integration for LaTeX compilation
- LaTeXML integration for TeX → HTML conversion
- Asset processing (TikZ/PDF → SVG)
- HTML post-processing and cleaning
- Fidelity scoring and quality assessment

### 🧪 [Testing & QA Agent](testing-agent.md)
**Focus**: Testing strategy, quality assurance, reliability
- Test suite design and implementation
- Unit, integration, and end-to-end testing
- Test data creation and management
- Performance testing and optimization
- CI/CD pipeline testing

### 📚 [Documentation Agent](docs-agent.md)
**Focus**: Technical documentation, user guides, API docs
- Technical documentation creation
- API documentation and examples
- User guides and tutorials
- Architecture and design documentation
- Troubleshooting and FAQ sections

### 🚀 [DevOps & Infrastructure Agent](devops-agent.md)
**Focus**: Deployment, infrastructure, CI/CD, operations
- Docker containerization and orchestration
- CI/CD pipeline setup and maintenance
- Environment configuration and management
- Monitoring and logging setup
- Security and compliance

## 🎯 How to Use These Agents

1. **Select the appropriate agent** based on your current task
2. **Review the agent's responsibilities** and focus areas
3. **Use the agent's guidance** for code standards and best practices
4. **Follow the agent's testing and quality criteria**
5. **Update TODO.md** as tasks are completed

## 🔄 Agent Collaboration

These agents are designed to work together:
- **API Agent** creates endpoints that **Conversion Agent** implements
- **Testing Agent** validates work from all other agents
- **Docs Agent** documents everything created by other agents
- **DevOps Agent** deploys and monitors the complete system

## 📝 Agent Updates

As the project evolves, these agent configurations should be updated to reflect:
- New technical requirements
- Additional responsibilities
- Updated dependencies
- Enhanced testing strategies
- Improved documentation standards

---

**Note**: These agents are living documents that should evolve with the project. Update them as new requirements emerge and the system grows in complexity.
