/* The connection diagram, shared by the published site and the portal's cast page.
 *
 * Two edge kinds are rendered distinguishably and never merged (FR-051, FR-052):
 * a solid line means "these two appear in stories together"; a dashed line means
 * "the author says they are connected", regardless of any story. A pair can carry
 * both, and then both are drawn.
 */
(function () {
  "use strict";

  function styles() {
    return [
      {
        selector: "node",
        style: {
          "background-color": "#7a3b2e",
          label: "data(label)",
          "font-size": "11px",
          "font-family": "Georgia, serif",
          color: "#2a2a2a",
          "text-valign": "bottom",
          "text-margin-y": 5,
          width: "mapData(stories, 0, 8, 14, 40)",
          height: "mapData(stories, 0, 8, 14, 40)",
        },
      },
      {
        selector: 'node[kind = "location"]',
        style: { "background-color": "#3d5a6c", shape: "round-rectangle" },
      },
      {
        selector: 'edge[kind = "co_appearance"]',
        style: {
          "line-color": "#b8b0a2",
          width: "mapData(weight, 1, 6, 1, 5)",
          "curve-style": "bezier",
        },
      },
      {
        selector: 'edge[kind = "stated"]',
        style: {
          "line-color": "#7a3b2e",
          "line-style": "dashed",
          width: 2,
          "curve-style": "bezier",
          label: "data(description)",
          "font-size": "9px",
          color: "#7a3b2e",
          "text-rotation": "autorotate",
        },
      },
      {
        selector: 'edge[kind = "stated"][?directed]',
        style: { "target-arrow-shape": "triangle", "target-arrow-color": "#7a3b2e" },
      },
    ];
  }

  function toElements(graph) {
    var elements = [];
    graph.nodes.forEach(function (node) {
      elements.push({ data: node });
    });
    graph.edges.forEach(function (edge, index) {
      var data = {
        id: edge.kind + ":" + index,
        source: edge.source,
        target: edge.target,
        kind: edge.kind,
        weight: edge.weight || 1,
        description: edge.description || "",
        directed: !!edge.directed,
      };
      elements.push({ data: data });
    });
    return elements;
  }

  function render(container, graph) {
    if (typeof cytoscape === "undefined") {
      return;
    }
    var cy = cytoscape({
      container: container,
      elements: toElements(graph),
      style: styles(),
      layout: { name: "cose", animate: false, padding: 30 },
      wheelSensitivity: 0.2,
    });

    cy.on("tap", "node", function (event) {
      var url = event.target.data("url");
      if (url) {
        var root = container.getAttribute("data-root") || "/";
        /* graph.json carries site-root-relative URLs; rebase onto this page. */
        window.location.href = url.charAt(0) === "/" ? root + url.slice(1) : url;
      }
    });
  }

  function start() {
    var container = document.getElementById("network");
    if (!container) return;

    var inline = container.getAttribute("data-graph-inline");
    if (inline) {
      render(container, JSON.parse(inline));
      return;
    }

    var source = container.getAttribute("data-graph");
    if (!source) return;
    fetch(source)
      .then(function (response) {
        return response.json();
      })
      .then(function (graph) {
        render(container, graph);
      })
      .catch(function () {
        container.textContent = "The diagram data could not be loaded.";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
