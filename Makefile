.PHONY: agent-deb web-deb debs

agent-deb:
	./packages/agent/build-deb.sh

web-deb:
	./packages/web/scripts/build-deb.sh

debs: agent-deb web-deb
