<template>
  <div class="sparql-template-page">
    <div
      class="button-row"
      v-if="!loading"
    >
      <div>
        <md-button
          class="md-icon-button"
          @click.native.prevent="selectQueryForVizEditor()"
        >
          <md-tooltip
            class="utility-bckg"
            md-direction="bottom"
          >
            Select current query and return to Viz Editor
          </md-tooltip>
          <md-icon>check</md-icon>
        </md-button>
        <md-button
          class="md-icon-button"
          @click.native.prevent="toVizEditor()"
        >
          <md-tooltip
            class="utility-bckg"
            md-direction="bottom"
          > Return to viz editor </md-tooltip>
          <md-icon>arrow_back</md-icon>
        </md-button>
      </div>
    </div>
    <md-toolbar>
      <h3 class="md-title">Query Template</h3>
    </md-toolbar>
    <div class="display">
      <md-button
        class="template-back"
        @click="shiftTemplate(-1)"
      >
        <md-icon>chevron_left</md-icon>
      </md-button>
      <md-button
        class="template-next"
        @click="shiftTemplate(1)"
      >
        <md-icon>chevron_right</md-icon>
      </md-button>
      <p class="display-text">
        <span
          v-for="(segment, index) in selectedTemplate.displaySegments"
          :key="index"
          >
          <span v-if="segment.type == TextSegmentType.TEXT" v-html="segment.text"></span>
          <span v-else>
            <select
              v-model="varSelections[segment.varName]"
              :id="segment.varName"
              :name="segment.varName"
            >
              <option
                v-for="(value, name) in selectedTemplate.options[segment.varName]"
                :key="name"
                :value="name"
              >
                {{name}}
              </option>
            </select>
          </span>
        </span>
      </p>
    </div>
    <div class="display-count-indicator">
      <p>Query template {{currentIndex + 1}} of {{totalTemplateCount}}</p>
    </div>
    <div class="query">
      <accordion
        :startOpen="false"
        title="SPARQL Query"
      >
        <yasqe :value="query" readonly="true"></yasqe>
      </accordion>
    </div>
    <div class="results">
      <accordion
        :startOpen="true"
        title="SPARQL Results"
      >
        <div v-if="results">
          <yasr :results="results"></yasr>
        </div>
        <md-progress-spinner
          v-else
          :md-diameter="30"
          :md-stroke="3"
          md-mode="indeterminate"
        ></md-progress-spinner>
      </accordion>
    </div>
  </div>
</template>

<script>
import yaml from "js-yaml";
import { mapMutations } from 'vuex';
import { querySparql } from "../../../utilities/sparql";
import { goToView, VIEW_URIS, DEFAULT_VIEWS } from "../../../utilities/views";
import debounce from "../../../utilities/debounce"

const TextSegmentType = Object.freeze({
  VAR: "var",
  TEXT: "text"
});

const stripQVarFormatting = formatted =>
  formatted
    .replace(/^{{/, "")
    .replace(/}}$/, "")
    .trim();
const qVarRegex = /({{[^{}]+}})/g;

const queryTemplates = {};
const confContext = require.context("./conf/", true, /\.ya?ml$/);
confContext.keys().forEach(function(filename) {
  const yamlContents = confContext(filename);
  const queryTemplate = yaml.load(yamlContents);
  queryTemplate.displaySegments = parseDisplayText(queryTemplate.display);
  const queryId = filename.slice(2).replace(/\.ya?ml$/, "");
  queryTemplates[queryId] = queryTemplate;
});

function parseDisplayText(displayText) {
  return displayText.split(qVarRegex).map(token => {
    let displaySegment;
    if (qVarRegex.test(token)) {
      displaySegment = {
        type: TextSegmentType.VAR,
        varName: stripQVarFormatting(token)
      };
    } else {
      displaySegment = {
        type: TextSegmentType.TEXT,
        text: token
      };
    }
    return displaySegment;
  });
}

export default {
  data() {
    return {
      queryTemplates,
      TextSegmentType,
      selTemplateId: Object.keys(queryTemplates)[0],
      query: "",
      varSelections: {},
      results: null,
      execQueryDebounced: debounce(this.execQuery, 300)
    };
  },
  computed: {
    templateIds() {
      return Object.keys(this.queryTemplates);
    },
    selectedTemplate() {
      return this.queryTemplates[this.selTemplateId];
    },
    currentIndex() {
      return this.templateIds.indexOf(this.selTemplateId)
    },
    totalTemplateCount() {
      return this.templateIds.length
    }
  },
  methods: {
    ...mapMutations('vizEditor', ['setQuery']),
    selectQueryForVizEditor() {
      this.setQuery(this.query)
      this.toVizEditor()
    },
    toVizEditor() {
      goToView(VIEW_URIS.CHART_EDITOR, DEFAULT_VIEWS.NEW)
    },
    shiftTemplate(amount) {
      let newIndex = this.currentIndex + amount;
      while (newIndex >= this.totalTemplateCount) {
        newIndex -= this.totalTemplateCount;
      }
      while (newIndex < 0) {
        newIndex += this.totalTemplateCount;
      }
      this.selTemplateId = this.templateIds[newIndex];
      console.log("shifted", newIndex, this.selTemplateId, this.templateIds);
    },
    populateSelections() {
      this.varSelections = Object.fromEntries(
        Object.entries(
          this.selectedTemplate.options
        ).map(([varName, varOpts]) => [varName, Object.keys(varOpts)[0]])
      );
    },
    buildQuery() {
      this.query = this.selectedTemplate.SPARQL.replace(qVarRegex, match => {
        const qVar = stripQVarFormatting(match);
        const selection = this.varSelections[qVar];
        return this.selectedTemplate.options[qVar][selection];
      });
    },
    async execQuery() {
      console.log("querying....");
      this.results = null;
      this.results = await querySparql(this.query);
      console.log("done", this.results);
    },
  },
  watch: {
    // The following reactive watchers are used due to limitations of not being
    // able to deep watch dependencies of computed methods.
    selectedTemplate: {
      handler: "populateSelections",
      immediate: true
    },
    varSelections: {
      handler: "buildQuery",
      immediate: true,
      deep: true
    },
    query: {
      immediate: true,
      handler: "execQueryDebounced"
    }
  }
};
</script>

<style lang="scss" scoped>
.sparql-template-page {
  max-width: 960px;
  margin: auto;
}
.display {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  height: 18em;
  .template-next {
    order: 1;
  }
  .display-text {
    max-height: calc(100% - 60px);
    overflow: auto;
    margin: 30px;
    font-size: 16px;
    line-height: 40px;
  }
}
.display-count-indicator {
  text-align: center;
  margin-bottom: 20px;
  font-weight: 500;
}
.accordion {
  margin-bottom: 20px;
}
</style>
