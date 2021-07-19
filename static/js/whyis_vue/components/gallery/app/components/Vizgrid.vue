<template>
    <div class="">
        <spinner :loading="loading" text='Loading...' v-if="loading"/>
        <div class="utility-roverflow" v-else>
            <div class="utility-content__result">
                <!-- TODO TIME TO RESULT -->
                <span v-if="otherArgs == null && results.length <= 1">{{results.length}} result (0.59 seconds)</span>
                <span v-else-if="otherArgs == null && results.length >= 2">About {{results.length}} results (0.59 seconds)</span>
                <span class="utility-color" v-else-if="otherArgs != null">Home > <strong> {{ otherArgs }}</strong> > About {{results.length}} results (0.59 seconds)</span>
                <span v-else>No result (0.59 seconds)</span>
            </div>
            <div class="viz-content">
                <md-card v-for="(result, index) in newResults" :key="index" class="btn--animated">
                    <!--<div class="utility-gridicon" v-if="authenticated && authenticated.admin=='True'">
                        <div @click.prevent="bookmark(result.name, true)" v-if="result.bookmark"><md-icon>bookmark</md-icon></div>
                        <div @click.prevent="bookmark(result.name, false)" v-else><md-icon>bookmark_border</md-icon></div>
                        <div @click.prevent="deleteChart(result)"><md-icon>delete_outline</md-icon></div>
                    </div>
                    <div class="utility-gridicon" v-else-if="authenticated">
                        <div @click.prevent="bookmark(result.name, true)" v-if="result.bookmark"><md-icon>bookmark</md-icon></div>
                        <div @click.prevent="bookmark(result.name, false)" v-else><md-icon>bookmark_border</md-icon></div>
                    </div>-->
                    <md-card-media-cover md-solid @click.native.prevent="navigate(result)" >
                        <md-card-media md-ratio="4:3" >
                        <img :src="getViewUrl(result.thumbnail)" :alt="result.label" v-if="result.thumbnail">
                        <img :src="$root.$data.root_url + 'static/images/rdf_flyer.svg'" :alt="result.label" v-else>
                        </md-card-media>
                        <md-card-area class="utility-gridbg">
                            <md-card-header class="utility-show_hide">
                                <span class="md-subheading">
                                    <strong>{{ result.label }}</strong>
                                </span>
                                <span class="md-body-1">{{ reduceDescription(result.description) }}</span>
                            </md-card-header>
                        </md-card-area>
                    </md-card-media-cover>
                </md-card>
            </div>
            <pagination v-if="results.length > basePage" :cpage="currentPage" :tpages="totalPages" />
        </div>
    </div>
</template>
<style scoped lang="scss" src="../../../../assets/css/main.scss"></style>
<script>
    import { EventServices, Slug } from '../../../../modules'
    import { getViewUrl } from '../../../../utilities/views'
    import pagination from './Pagination'
    import axios from 'axios'
    export default {
        name: "viz-grid",
        props:{
          authenticated: {
            type: Boolean,
            require: true
          },
          instancetype: {
            type: String,
            require: true
          }
        },
        data() {
            return {
                results: [],
                newResults: [],
                loading: false,
                loadError: false,
                otherArgs: null,
                totalPages: 1,
                currentPage: 1,
                basePage: 10,
                perPage: 10,
            }
        },
        watch: {
            results(newValues, oldValues){
                if(newValues && newValues != oldValues){
                    const length = newValues.length;
                    let tpages = Math.round(length/this.basePage)
                    if(length <= this.basePage){
                       this.totalPages = 1;
                    } else if(length%this.basePage == 0){
                        this.totalPages = tpages;
                    } else if(length%this.basePage <= 4) {
                        this.totalPages = tpages + 1;
                    } else {
                        this.totalPages = tpages;
                    }
                }
                this.showResults()
            },
            currentPage(newValues, oldValues){
                if(newValues != oldValues){
                    this.showResults()
                }
            }
        },
        components: {
            pagination
        },
        methods: {
            async showResults(){
                this.perPage = this.currentPage * this.basePage
                const newArr = [];
                await this.results.map((e,i) => {
                    if(i+1 <= this.perPage && i+1 > this.perPage - this.basePage){
                        newArr.push(e)
                    }
                })
                return this.newResults = newArr;
            },
            getViewUrl(uri, view) { return getViewUrl(uri, view) },
            navigate(args) {
                return window.location = args.identifier
            },
            reduceDescription(args) {
                let arr, arrSplice, res
                arr = args.split(" ")
                arr.splice(15)
                arrSplice = arr.reduce((a,b) => `${a} ${b}`, "")
                res = Slug(arrSplice)
                return `${res}...`
            },
            bookmark(args, exist){
                return EventServices.createChartBookMark(args, exist);
            },
            deleteChart(chart){
                return EventServices.$emit("dialoguebox", {status: true, delete: true, title: "Delete", message: `Are you sure you want to delete this chart?`, chart})
            },

        },
        async mounted (){
            this.loading = true
            // Commenting out VOTD until we can figure out how to do it generically.
            //const vvodd = false // await EventServices.getVizOfTheDayStatus()
            //const result = await EventServices.fetchInstances(this.type)
            const result = await axios.get(`${ROOT_URL}about`,
                                           { params: {
                                               view: "instances",
                                               uri: this.instancetype
                                             }
                                           })
            this.results = result.data
            //if(result.length > 0 && vvodd.status == true){
            //    let viz = result[0];
            //    if("backup" in viz){
            //        this.loading = false
            //        // return window.location = viz.backup.uri
            //    }
            //}
            this.loading = false
        },
        //beforeMount(){
        //    return this.loadAllInstances()
        //},
        created(){
            EventServices
            .$on("appstate", (data) => {
                this.results = data.filter((el) => el.enabled == true)
            })
            .$on("filterexistcancel", (data) => this.results = data)
            .$on("filterexist", (data) => this.results = data)
            .$on("chartpagination", (data) => this.currentPage = data)
        }
    }
</script>
