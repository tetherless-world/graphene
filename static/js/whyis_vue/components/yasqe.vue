<template>
    <div class="yasqe"></div>
</template>

<script>
import Vue from "vue"

export default Vue.component('yasqe', {
    props: {
        value: {
            type: String,
            default: () => ""
        },
        endpoint: {
            type: String,
            default: () => "/sparql"
        },
        showBtns: {
            type: Boolean,
            default: false
        },
        readOnly: {
            type: Boolean,
            default: false
        }
    },
    data() {
        return {
            editorValue: this.value
        }
    },
    mounted () {
        const yasqeContext = this
        this.yasqe = window.YASQE(this.$el, {
            persistent: null,
            sparql: {
                showQueryButton: !this.showBtns,
                endpoint: this.endpoint,
                requestMethod: "POST",
                callbacks: {
                    error (error) {
                        console.error('YASQE query error', error)
                        yasqeContext.$emit('query-error', error)
                    },
                    success (resp) {
                        yasqeContext.$emit('query-success', resp)
                    },
                }
            },
            readOnly: this.readOnly,
        })
        this.yasqe.setValue(this.value)
        this.yasqe.on('changes', () => {
            this.editorValue = yasqeContext.yasqe.getValue()
            yasqeContext.$emit('input', this.editorValue)
        })
        this.yasqe.setSize("100%", "100%")
    },
    watch: {
        value(value) {
            if (value !== this.editorValue) {
                this.yasqe.setValue(value)
            }
        }
    }
})
</script>
